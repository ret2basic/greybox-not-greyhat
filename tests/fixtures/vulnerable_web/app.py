import os

import requests
from flask import Flask, request, send_file

app = Flask(__name__)


@app.route("/download/<path:name>", methods=["GET"])
def download():
    path = request.args["path"]
    return send_file(path)


@app.post("/jobs")
def run_job(command: str):
    os.system(command)
    return {"ok": True}


def unsafe_client():
    return requests.get("https://internal.invalid", verify=False)


if __name__ == "__main__":
    app.run(debug=True)
