#!/bin/bash
# ANIMA ROS2 Simulation — Startup Script
# Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs
set -e

source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-10}
export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}

WORLD_FILE=${WORLD_FILE:-warehouse_sensors.sdf}

echo "=== ANIMA Sim: $WORLD_FILE ==="

# 1. Start Gazebo (background)
gz sim -s -r "/anima_ws/worlds/$WORLD_FILE" &
GZ_PID=$!
sleep 8

# 2. Spawn robot with sensors
echo "=== Spawning robot ==="
gz service -s /world/warehouse/create \
  --reqtype gz.msgs.EntityFactory \
  --reptype gz.msgs.Boolean \
  --req "sdf_filename: \"/anima_ws/models/anima_mobile_base/model.sdf\", name: \"anima_robot\", pose: {position: {x: 0, y: 0, z: 0.3}}" \
  --timeout 5000 || echo "Spawn failed (model might not exist)"

sleep 2

# 3. Start GZ→ROS2 bridge (background) — all sensors + 3 cameras
echo "=== Starting GZ Bridge ==="
ros2 run ros_gz_bridge parameter_bridge \
  /camera@sensor_msgs/msg/Image[gz.msgs.Image \
  /overhead_camera@sensor_msgs/msg/Image[gz.msgs.Image \
  /side_camera@sensor_msgs/msg/Image[gz.msgs.Image \
  /depth@sensor_msgs/msg/Image[gz.msgs.Image \
  /imu@sensor_msgs/msg/Imu[gz.msgs.IMU \
  /scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan \
  /odom@nav_msgs/msg/Odometry[gz.msgs.Odometry \
  "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist" \
  /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock \
  /joint_states@sensor_msgs/msg/JointState[gz.msgs.Model \
  --ros-args \
  -r /camera:=/camera/rgb/image_raw \
  -r /overhead_camera:=/camera/overhead/image_raw \
  -r /side_camera:=/camera/side/image_raw \
  -r /scan:=/lidar/scan \
  -r /depth:=/depth/image &

sleep 3

# 4. Compress ALL camera feeds (raw 900KB → JPEG ~30KB each)
echo "=== Starting image compressors ==="
python3 -c "
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage

class MultiImageCompressor(Node):
    def __init__(self):
        super().__init__('anima_image_compressor')
        self.cameras = {
            '/camera/rgb/image_raw': '/camera/rgb/image_raw/compressed',
            '/camera/overhead/image_raw': '/camera/overhead/image_raw/compressed',
            '/camera/side/image_raw': '/camera/side/image_raw/compressed',
        }
        self.pubs = {}
        self.frame_counts = {}
        for src, dst in self.cameras.items():
            self.pubs[src] = self.create_publisher(CompressedImage, dst, 1)
            self.frame_counts[src] = 0
            self.create_subscription(Image, src, lambda msg, s=src: self.callback(s, msg), 1)
            self.get_logger().info(f'Compressing {src} -> {dst}')

    def callback(self, src, msg):
        self.frame_counts[src] += 1
        if self.frame_counts[src] % 3 != 0:
            return
        try:
            import cv2
            import numpy as np
            if msg.encoding == 'rgb8':
                img = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(msg.height, msg.width, 3)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            else:
                img = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(msg.height, msg.width, 3)
            _, jpeg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 60])
            comp = CompressedImage()
            comp.header = msg.header
            comp.format = 'jpeg'
            comp.data = jpeg.tobytes()
            self.pubs[src].publish(comp)
        except Exception as e:
            self.get_logger().warn(f'Compression error on {src}: {e}')

rclpy.init()
node = MultiImageCompressor()
rclpy.spin(node)
" &

sleep 2

# 5. Start Rosbridge (foreground — keeps container alive)
echo "=== Starting Rosbridge on 0.0.0.0:9090 ==="
ros2 launch rosbridge_server rosbridge_websocket_launch.xml \
  address:=0.0.0.0 \
  port:=9090
