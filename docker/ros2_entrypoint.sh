#!/bin/bash
set -e

# Source ROS2
source /opt/ros/humble/setup.bash

# Source workspace if built
if [ -f /anima_ws/install/setup.bash ]; then
    source /anima_ws/install/setup.bash
fi

exec "$@"
