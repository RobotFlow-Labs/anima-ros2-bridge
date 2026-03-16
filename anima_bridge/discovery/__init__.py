"""ANIMA Smart Discovery -- auto-identifies robots, sensors, and capabilities.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

This is not just topic listing. This is robot intelligence:
- Plug in ANY ROS2 robot → ANIMA identifies what it is
- Detect sensor types from topic signatures
- Measure real-time topic rates
- Build hardware_manifest.yaml automatically
- Recommend which ANIMA modules to use
- Monitor health continuously
"""

from anima_bridge.discovery.fingerprint import RobotFingerprinter
from anima_bridge.discovery.scanner import CapabilityScanner

__all__ = ["CapabilityScanner", "RobotFingerprinter"]
