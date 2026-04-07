#!/bin/bash

FILE="../configs/config-p107-runtime.yaml"

echo "config file $FILE"

sed -i '/^exit:/ s/false/True/I' $FILE

echo "exit is changed to True, so the engine will be stopped"
echo "check the logs ...."
