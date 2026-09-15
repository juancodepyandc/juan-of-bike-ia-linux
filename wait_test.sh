#!/bin/bash
/home/juan/AuroraIA/cycle_app_venv/bin/python test_happy.py > /tmp/happy_launch.log
# Wait 10 seconds for Kaggle API to register it
sleep 10
# Find the exact kernel slug from the log
SLUG=$(grep -o "aurora-3d-[a-z0-9]*" /tmp/happy_launch.log | head -n 1)
echo "Launched $SLUG, waiting for completion..."

while true; do
    STATUS=$(/home/juan/AuroraIA/cycle_app_venv/bin/kaggle kernels status evanpasdeloup/$SLUG)
    echo "$(date) - $STATUS"
    if [[ "$STATUS" == *"complete"* ]]; then
        echo "SUCCESS!"
        break
    fi
    if [[ "$STATUS" == *"error"* ]] || [[ "$STATUS" == *"ERROR"* ]]; then
        echo "FAILED!"
        /home/juan/AuroraIA/cycle_app_venv/bin/kaggle kernels output evanpasdeloup/$SLUG -p /tmp/err_log
        tail -n 20 /tmp/err_log/$SLUG.log
        break
    fi
    sleep 15
done
