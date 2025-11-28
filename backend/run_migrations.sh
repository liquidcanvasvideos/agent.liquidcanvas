#!/bin/bash
# Migration script - can be run manually or on startup
cd /app
alembic upgrade head

