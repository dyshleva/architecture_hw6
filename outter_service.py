from fastapi import FastAPI, HTTPException
from influxdb_client import InfluxDBClient, Point
from datetime import datetime
import re, requests, pytz

app = FastAPI()

influx_client = InfluxDBClient(url="http://influx:8086",
                               token="supertoken",
                               org="architecture")

logger = influx_client.write_api()


def validator(question):
    case = None
    info = None

    yes_no_starters = r"^(do|does|did|is|are|was|were|can|could|would|should|will|have|has|had)\b"
    yes_no_checker = question.strip().endswith("?") and re.match(
        yes_no_starters, question.strip(), re.IGNORECASE)

    fraud_keywords = [
        "bank account", "password", "pin", "transfer money", "send money"
    ]
    fraud_checker = any(keyword.lower() in question.lower()
                        for keyword in fraud_keywords)

    phone_pattern = r"(\+?\d{1,3}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?){2,4}\d{2,4}"
    credit_card_pattern = r"\b(?:\d[ -]*?){13,16}\b"
    personal_data = bool(re.search(phone_pattern, question)) or bool(
        re.search(credit_card_pattern, question))

    if not yes_no_checker:
        case = "Wrong question"
        info = "Question do not formulated as yes/no question"
        return case, info
    if fraud_checker:
        case = "Fraud"
        info = "Fraud detected in question"
        return case, info
    if personal_data:
        case = "Personal data"
        info = "Personal data detected in question"
        return case, info

    return case, info


def create_report(reason, info):
    now = datetime.now(pytz.timezone("Europe/Kyiv"))
    formatted = now.strftime(
        '%Y-%m-%d %H:%M:%S.') + f"{int(now.microsecond / 1000):03d}"

    with open(f"./error_reports/alert_{formatted}.txt", "w") as alert:
        alert.write(f"""Time: {formatted}\nReason: {reason}\nDescription: {info}\n""")


def create_point(level, message):
    return Point("logs") \
            .tag("level", level) \
            .field("message", message) \
            .time(datetime.now(pytz.timezone("Europe/Kyiv")))


@app.get("/")
def description():
    logger.write(bucket="logging_bucket",
                 org="architecture",
                 record=create_point("INFO (outter)",
                                     f"Description endpoint triggered"))
    return {"message": "service which has answer for all your questions"}


@app.get("/health")
def healthcheck():
    logger.write(bucket="logging_bucket",
                 org="architecture",
                 record=create_point("INFO (outter)",
                                     f"Healthcheck endpoint triggered"))
    return {"status": 200}


@app.post("/prediction")
def make_prediction(question: str):
    logger.write(bucket="logging_bucket",
                 org="architecture",
                 record=create_point(
                     "INFO (outter)",
                     f"Prediction submitter endpoint triggered"))

    case, info = validator(question)

    if case:
        create_report(case, info)
        logger.write(bucket="logging_bucket",
                     org="architecture",
                     record=create_point(
                         "ERROR (outter)",
                         f"Forbidden type of input was provided"))
        raise HTTPException(403, detail=f"Forbidden type of input: {info}")
    
    status_code = requests.get("http://inner:8080/health")

    if status_code.json()["status"] != 200:
        logger.write(bucket="logging_bucket",
             org="architecture",
             record=create_point(
                 "ERROR (outter)",
                 f"Prediction service went down"))
        raise HTTPException(500, f"Something went wrong with prediction service")

    response = requests.post(f"http://inner:8080/prediction?question={question}")

    return response.json()


@app.get("/status")
def prediction_status(prediction_id: str):
    logger.write(bucket="logging_bucket",
                 org="architecture",
                 record=create_point("INFO (outter)",
                                     f"Status checker endpoint triggered"))
    
    status_code = requests.get("http://inner:8080/health")

    if status_code.json()["status"] != 200:
        logger.write(bucket="logging_bucket",
             org="architecture",
             record=create_point(
                 "ERROR (outter)",
                 f"Prediction service went down"))
        raise HTTPException(500, f"Something went wrong with prediction service")

    response = requests.get(
        f"http://inner:8080/status?prediction_id={prediction_id}")

    return response.json()
