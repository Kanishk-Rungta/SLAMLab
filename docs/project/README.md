# Project overview

**Edge-Based Multi-Robot System for Collaborative SLAM and Autonomous Task Coordination** is Team 98's final-year research project. SLAMLab grew from this work and provides a public platform for learning, simulation, visualization and reproducible SLAM experiments.

## What is our project about?

We are investigating how a team of indoor robots can build a shared map, estimate their positions and coordinate autonomous tasks such as exploring different areas. Each robot needs to understand its surroundings, identify obstacles and contribute useful observations to a shared understanding of the environment.

Our current work focuses on that mapping and exploration foundation in **Webots, a robot simulator**. SLAM stands for **simultaneous localization and mapping**: estimating where a robot is while building a map. Reliable collaborative mapping, integrated autonomous task coordination and physical robot deployment require further development and evaluation.

**Edge-based** describes the intended processing approach: handle observations on or near each robot and exchange useful information between robots. Physical deployment must establish the actual computing, memory and communication requirements; the title does not imply those measurements are complete.

SLAMLab is the learning and experimentation platform that grew from this research. Its playground explains individual ideas, and its separate Landmark Lab example lets visitors inspect recorded simulation data. Progress on these teaching tools is distinct from progress on the integrated multi-robot system.

## Project statement

Develop and evaluate an edge-based multi-robot approach to collaborative SLAM and autonomous task coordination. Investigate local perception, shared mapping and coordinated exploration in simulation before progressing to measured physical robot integration.

## Problem statement

Mapping a large indoor environment requires robots to estimate their positions while observing unfamiliar rooms, obstacles and changing surroundings. Errors in motion estimates can accumulate, and separate robots may describe the same space using different coordinate systems. Combining those observations into a consistent shared map is a central challenge.

A multi-robot system must also decide which areas each robot should explore, avoid unnecessary duplication and exchange information within practical computing and communication limits. The project investigates how processing on or near the robots can support collaborative SLAM and autonomous task coordination under these constraints.

## Project objectives

- Investigate indoor localization, mapping and exploration without LiDAR.
- Develop and evaluate a foundation for combining robots' observations into a consistent shared map.
- Investigate edge-based processing and measure computing, memory and communication requirements.
- Work toward autonomous task coordination for exploration and mapping, including reducing duplicated effort.
- Progress from simulation to measured physical-robot evaluation.
- Make reusable SLAM concepts, experiments and evaluation tools accessible through SLAMLab.

## Methodology

The project follows a simulation-first research approach. The methodology connects current mapping work with planned validation of collaboration, edge deployment and task coordination:

1. **Observe locally:** use visual and motion observations to understand each robot's surroundings, accounting for uncertainty and limited visibility.
2. **Localize and map:** estimate robot motion and represent observed space; assess localization and map quality separately.
3. **Explore and collaborate:** investigate navigation, obstacle handling, sharing information and bringing local maps into consistent coordinates.
4. **Coordinate tasks:** develop and evaluate how robots can divide exploration work using the available map and shared information. Integrated autonomous task coordination remains a development stage.
5. **Evaluate:** compare recorded estimates with independent reference data under declared conditions. Assess map quality, localization, navigation and resource use while keeping observations, interpretations and limitations explicit.
6. **Progress toward edge hardware:** identify and calibrate physical interfaces, measure local processing and communication requirements, evaluate one robot, then investigate a cooperative physical system.

SLAMLab supports this learning and evaluation workflow through browser experiments, a separate landmark EKF-SLAM example in Webots, recorded replays and trajectory evaluation tools. Its two-robot Landmark Lab example uses independent estimators and does not demonstrate collaborative SLAM.

## Project guide

**Dr. Vidhya Balasubramanian** guides Team 98's final-year research project.

## Team details

**Team 98**

| Team member | Student ID |
| --- | --- |
| Konduru Hemesh | CB.SC.U4CSE23724 |
| Manu Santosh | CB.SC.U4CSE23729 |
| Rithvik Mukka | CB.SC.U4CSE23731 |
| Kanishk Rungta | CB.SC.U4CSE23761 |
| Praneeth Gorugantu | CB.SC.U4CSE23769 |

SLAMLab is developed and maintained collaboratively by the entire project team, with shared contributions to integration and evaluation. The software citation credits the project team collectively. Original research authors retain attribution in the algorithm profiles and references.

## Project progress

**Current stage: experimental mapping and exploration in simulation.** The foundation uses two robots in Webots. Reliable collaborative mapping, integrated autonomous task coordination and measured physical mapping performance remain to be established.

The status below separates the original research, the SLAMLab teaching platform and future goals. “Experimental” means work exists but still needs reliability and validation; “pending” means the stated integration or measurement remains to be completed.

| Area | Current status |
| --- | --- |
| Original research foundation | Experimental two-robot mapping and exploration in Webots. Map quality, localization reliability and extended operation need improvement. |
| SLAMLab learning platform | Twelve guided lessons, five interactive browser models, seven algorithm profiles and documentation are available. |
| Landmark Lab | Published one-robot and two-independent-robot Webots recordings, with trajectory metrics and replay bundles. These are separate from the original cooperative research system. |
| Native research integrations | Integration guides and selected adapters are available. Native build and execution validation in SLAMLab remain pending. No research-system ranking is established. |
| Physical robot deployment | bStem is the hardware target. Connectivity work has been reported; physical mapping integration, calibration and measured performance remain pending. |
| Edge deployment | Local processing is part of the intended architecture. Physical computing, memory and communication requirements still need measurement. |
| Autonomous task coordination | A future integration and evaluation stage. Reliable autonomous allocation of exploration and mapping tasks is not an established capability of the active foundation. |

### What comes next?

1. Improve mapping quality and the reliability of position estimates.
2. Evaluate navigation, obstacle handling and recovery in a wider range of situations.
3. Validate the native research integrations under comparable conditions.
4. Integrate and calibrate the physical robot, then measure mapping performance, local computing and communication requirements.
5. Develop and evaluate autonomous task coordination for cooperative exploration and mapping.

These are development stages, not completed milestones or a promised completion date. No overall completion percentage or ranking against other SLAM systems is established.

## Documentation

- [SLAM fundamentals](../fundamentals/README.md): start with the main concepts.
- [Your first SLAM experiment](../learning/first-slam.md): run the separate Landmark Lab example.
- [Landmark Lab guide](../../examples/landmark-slam/README.md): inspect the sensor contract and saved outputs.
- [SLAM evaluation](../benchmarking/metrics.md): understand trajectory association, alignment, ATE, RPE and coverage.
- [Research references](../references/README.md): find original publications and upstream attribution.

## Repository link

[Explore the SLAMLab repository](https://github.com/Kanishk-Rungta/SLAMLab) for the platform source, reviewed simulation resources, setup instructions and contribution guidance.

## Demonstration videos

No demonstration videos are currently available. Recorded Landmark Lab data can be explored interactively in Studio; these replays are separate from demonstration videos.
