# Project overview

**Autonomous Swarm Robotic System for Intelligent Mapping and Cleaning of Large Indoor Environments** is Team 98's final-year research project. SLAMLab grew from this work and provides a public platform for learning, simulation, visualization and reproducible SLAM experiments.

## What is our project about?

We are investigating how a team of indoor robots can understand a building and eventually coordinate its cleaning. Before a robot can clean a room usefully, it needs to estimate where it is, identify obstacles and keep a map of the space it has observed. Several robots also need to share useful information about that space.

Our current work focuses on that mapping and exploration foundation in **Webots, a robot simulator**. SLAM stands for **simultaneous localization and mapping**: estimating where a robot is while building a map. Reliable cooperative cleaning and physical robot deployment are later stages.

SLAMLab is the learning and experimentation platform that grew from this research. Its playground explains individual ideas, and its separate Landmark Lab example lets visitors inspect recorded simulation data. Progress on these teaching tools is distinct from progress on the complete cleaning system.

## Project statement

Investigate how robots can build an understanding of indoor spaces, share useful mapping information and work toward coordinated cleaning. Develop and evaluate the mapping foundation in simulation before progressing to physical robot integration.

## Problem statement

Large indoor facilities contain multiple rooms, different surfaces and changing levels of human activity. A robot needs to understand its surroundings and estimate its position before it can perform useful cleaning work. Multiple robots also need to coordinate their efforts and contribute to a shared understanding of the environment.

## Project objectives

- Investigate indoor mapping and exploration without LiDAR.
- Develop a foundation for robots to contribute information about a shared space.
- Work toward coordinated cleaning that responds to changing indoor needs.
- Progress from simulation to measured physical-robot evaluation.
- Make reusable SLAM concepts, experiments and evaluation tools accessible through SLAMLab.

## Methodology

The project follows a simulation-first research approach:

1. **Observe:** use visual and motion observations to understand the surroundings, accounting for uncertainty and limited visibility.
2. **Localize and map:** estimate robot motion and represent observed space; assess localization and map quality separately.
3. **Explore and collaborate:** investigate navigation, obstacle handling and sharing information between robots.
4. **Evaluate:** compare recorded estimates with independent reference data under declared conditions. Keep observations, interpretations and limitations explicit.
5. **Progress toward hardware:** identify and calibrate physical interfaces, evaluate one robot, then investigate cooperation and integrated cleaning.

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

The team shares development, integration and evaluation. Kanishk Rungta is the SLAMLab platform maintainer. Original research authors retain attribution in the algorithm profiles and references.

## Project progress

**Current stage: experimental mapping and exploration in simulation.** The foundation uses two robots in Webots. The project has not yet established a complete cooperative cleaning system or measured physical mapping performance.

The status below separates the original research, the SLAMLab teaching platform and future goals. “Experimental” means work exists but still needs reliability and validation; “pending” means the stated integration or measurement remains to be completed.

| Area | Current status |
| --- | --- |
| Original research foundation | Experimental two-robot mapping and exploration in Webots. Map quality, localization reliability and extended operation need improvement. |
| SLAMLab learning platform | Twelve guided lessons, five interactive browser models, seven algorithm profiles and documentation are available. |
| Landmark Lab | Published one-robot and two-independent-robot Webots recordings, with trajectory metrics and replay bundles. These are separate from the original cooperative research system. |
| Native research integrations | Integration guides and selected adapters are available. Native build and execution validation in SLAMLab remain pending. No research-system ranking is established. |
| Physical robot deployment | bStem is the hardware target. Connectivity work has been reported; physical mapping integration, calibration and measured performance remain pending. |
| Cooperative cleaning | A future integration and evaluation stage. Complete cleaning missions are not an established capability of the active mapping foundation. |

### What comes next?

1. Improve mapping quality and the reliability of position estimates.
2. Evaluate navigation, obstacle handling and recovery in a wider range of situations.
3. Validate the native research integrations under comparable conditions.
4. Integrate and calibrate the physical robot, then measure its performance.
5. Develop and evaluate cooperative task execution and cleaning.

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
