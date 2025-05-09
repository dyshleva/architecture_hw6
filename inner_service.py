from time import sleep
from fastapi import FastAPI, HTTPException
from celery import Celery
from celery.result import AsyncResult
from influxdb_client import InfluxDBClient, Point
from datetime import datetime
import pytz

app = FastAPI()

influx_client = InfluxDBClient(url="http://influx:8086",
                               token="supertoken",
                               org="architecture")

logger = influx_client.write_api()

celery = Celery("executor",
                broker="redis://redis:6379/0",
                backend="redis://redis:6379/0")


def create_point(level, message):
    return Point("logs") \
            .tag("level", level) \
            .field("message", message) \
            .time(datetime.now(pytz.timezone("Europe/Kyiv")))


@celery.task(bind=True)
def get_prediction(self, question):
    self.update_state(state="IN PROGRESS")

    try:
        magic_number = len(question) // 2 * 8 % 9
        sleep(5)

        if magic_number < 4:
            return {"prediction": "The answer for your question is NO"}
        else:
            return {"prediction": "The answer for your question is YES"}

    except Exception as e:
        self.update_state(state="FAILED")
        raise HTTPException(500, f"Something went wrong: {e}")


@app.get("/")
def description():
    logger.write(bucket="logging_bucket",
                 org="architecture",
                 record= create_point("INFO (inner)",
                                           f"Description endpoint triggered"))
    return {"message": "service to generate a prediction based on question"}


@app.get("/health")
def healthcheck():
    logger.write(bucket="logging_bucket",
                 org="architecture",
                 record= create_point("INFO (inner)",
                                           f"Healthcheck endpoint triggered"))
    return {"status": 200}


@app.post("/prediction")
def send_prediction(question: str):
    logger.write(bucket="logging_bucket",
                 org="architecture",
                 record=
                 create_point("INFO (inner)",
                              f"Prediction submitter endpoint triggered"))
    prediction = get_prediction.delay(question)
    logger.write(bucket="logging_bucket",
             org="architecture",
             record=
             create_point("INFO (inner)",
                          f"Prediction {prediction.id} was submitted"))
    return {"prediction_id": prediction.id, "status": "ACCEPTED"}


@app.get("/status")
def prediction_status(prediction_id: str):
    logger.write(bucket="logging_bucket",
                 org="architecture",
                 record=
                 create_point("INFO (inner)", f"Status checker endpoint triggered"))
    prediction = AsyncResult(prediction_id, app=celery)

    if prediction.status == "FAILED":
        logger.write(bucket="logging_bucket",
                     org="architecture",
                     record=
                     create_point("ERROR (inner)", f"Prediction generation failed"))
        return {
            "prediction_id": prediction.id,
            "status": prediction.status,
            "details": prediction.info,
            "prediction": prediction.get()
        }

    logger.write(bucket="logging_bucket",
                 org="architecture",
                 record= create_point("INFO (inner)", f"Prediction was checked"))
    return {
        "prediction_id": prediction.id,
        "status": prediction.status,
        "prediction": prediction.get()
    }
