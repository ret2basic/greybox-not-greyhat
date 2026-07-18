const express = require("express");
const app = express();

app.patch("/accounts/:id", updateAccount);
app.post("/webhook/provider", receiveEvent);
