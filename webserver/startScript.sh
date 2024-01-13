#! /bin/bash
umask 000
uvicorn main:app --host 0.0.0.0 --port 8080 --reload