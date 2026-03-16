# Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs
"""Setuptools installer for the anima_discovery ROS2 package."""

from setuptools import find_packages, setup

PACKAGE_NAME = "anima_discovery"

setup(
    name=PACKAGE_NAME,
    version="0.1.0",
    packages=find_packages(exclude=["tests"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{PACKAGE_NAME}"]),
        (f"share/{PACKAGE_NAME}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="AIFLOW LABS LIMITED",
    maintainer_email="ilessio@aiflowlabs.io",
    description="ANIMA ROS2 discovery node — publishes robot capability manifests.",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "anima_discovery_node = anima_discovery.discovery_node:main",
        ],
    },
)
