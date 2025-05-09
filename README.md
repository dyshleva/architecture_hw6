### System Architecture
This application simulates working of llm. The main idea: to answer to yes/no question (randomly). Each request has fixed processing time - 5 seconds

1. Outter service - service which can be used by user. It has alerting system, which checks whether input is valid (valid question, no dangerous data, no personal data). It accepts user requests and send them to inner service.
2. Inner service - service which processes user requests and delegates tasks to celery workers. Also, it receives tasks from workers and send them back to outter service.
3. Redis - key-value database used as storage for tasks results and as a queue for task submission. Workers pull tasks from redis, inner service pulls task results.
4. Influx - time-series database, all services can produce logs (except redis), so all these logs are stored in Influx with timestampts.
5. Celery workers - used to process tasks.
![overview](/img/overview.png)

All endpoints in outter service and all endpoints, excpet ```get_prediction```, in inner service are synchronous. Only ```get_prediction``` is asynchronous, because it is celery task which means it is executed asynchronously in the background by a worker.

### Resource Scaling Estimation
For low-I/O operations (e.g., submitting tasks), a small number of inner and output services instances is sufficient. Since Celery workers can handle multiple tasks concurrently, we also don't need many worker instances.

- **10 Connections**:  
    Default setup is enough — 2 workers can handle more than 100 tasks in 1 minute.

- **50 Connections**:  
    The default setup is sufficient, but we may need to vertically scale the InfluxDB instance to handle the increased volume of logs.

- **100+ Connections**:  
    Requires broader scaling:  
    - **Client Service**: 2–3 instances + autoscaling + load balancer  
    - **Business Service**: 2–3 instances 
    - **InfluxDB**: move to clustered setup for write scalability and retention
    - **Redis**: move to cluster setup
    - **Celery Workers**: up to 6 workers, consider autoscaling

**Sum up.** Only in the case of 100 or more simultaneous connections does the system require significant horizontal scaling. At that point, we need to scale out client and business services to handle the increased load, add more Celery workers to maintain low task processing latency, and consider distributing InfluxDB and Redis or using a managed solution to ensure it can handle the high volume of log data efficiently.

### RESULTS
1. Run ```podman compose up```:
![run](/img/run.png)
2. App will be accessible on address ```http://localhost:8000```
3. Run ```curl 'http://localhost:8000/'``` to get description:
![desc](/img/desc.png)
4. Run ```curl -X POST 'http://localhost:8000/prediction?question=Will%20I%20live%forever?'```:
![pred](/img/pred.png)
5. Run ```curl 'http://localhost:8000/status?prediction_id={prediction_id}'```:
![status](/img/status.png)
6. Alert system ```curl -X POST 'http://localhost:8000/prediction?question=what%20is%20your%20name?'```:
![alert](/img/alert.png)
![file](/img/alert_file.png)
7. Logs ```influx query 'from(bucket: "logging_bucket") |> range(start: -12h)'``` (run in influx container):
![logs](/img/logs.png)
8. Workers process tasks (we will generate more tasks to see more logs inside each worker):
![worker](/img/worker1.png)
![worker](/img/worker2.png)
9. Clean environment ```podman compose down```:
![end](/img/end.png)