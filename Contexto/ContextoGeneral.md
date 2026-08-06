# Local Sports - Complete Project Context

> This document contains the complete context of the project up to the end of Deliverable 1. It is intended to be used to migrate the project to another ChatGPT conversation without losing context.

---

# 1. General Information

## Course

Software Engineering

The course follows an Agile Software Development approach using **Scrum**.

The team works using:

- Product Backlog
- Sprint Backlog
- Weekly Scrum Meetings
- Sprint Retrospectives
- GitHub Projects / Issues

---

## Team

- 3 members

---

## Project Name

**Local Sports**

---

# 2. Project Overview

Local Sports is a web application designed to simplify the organization of recreational football matches.

Instead of using WhatsApp groups or social media, users can:

- Create matches
- Join matches
- Request to join private matches
- Confirm attendance
- View participants
- Manage waiting lists
- Organize matches from one centralized platform

The long-term differentiator of the project is a **statistics-based matchmaking system** capable of recommending matches according to the player's performance.

**IMPORTANT**

The matchmaking system is **NOT part of the MVP**.

---

# 3. Problem Statement

People currently organize recreational football matches using WhatsApp groups and social media.

Problems include:

- Difficult to find enough players
- Difficult to coordinate schedules
- Last-minute cancellations
- No centralized participant management
- Manual organization

---

# 4. Product Vision

Create a centralized web platform that simplifies organizing recreational football matches.

---

# 5. Value Proposition

Unlike WhatsApp groups, Local Sports provides:

- Organized match management
- Centralized participant lists
- Attendance confirmation
- Waiting lists
- Automatic player replacement
- Future intelligent matchmaking recommendations

---

# 6. MVP Scope

The MVP ONLY focuses on solving the organization problem.

Authentication is considered a technical requirement.

The following are NOT part of the MVP:

- Matchmaking
- Statistics
- Ratings
- Chat
- Payments
- Smartwatch integration

---

# 7. User Roles

## Player

Capabilities:

- Browse matches
- Search matches
- Join matches
- Leave matches
- Confirm attendance
- View participants

---

## Captain

Capabilities:

- Create matches
- Configure match details
- Accept / Reject requests
- Cancel matches

---

# 8. Technology Stack

Backend

- Python 3.12
- Django

Frontend

- HTML
- CSS
- JavaScript
- Bootstrap

Database

Development

- SQLite

Production

- PostgreSQL

Version Control

- Git
- GitHub

Methodology

- Scrum

Deployment (planned)

- Docker

Communication

- HTTP / HTTPS

---

# 9. Current Project Status

Deliverable 1 has been completed.

The following sections were delivered:

- Introduction
- Product Perspective
- Product Functions
- User Characteristics
- Limitations
- Functional Requirements
- Usability Requirements
- Logical Database Requirements
- Video
- Sprint Retrospective

The project is now entering implementation.

---

# 10. Functional Requirements

There are 30 requirements.

## Must Have (FR1 - FR12)

Sprint 1

FR1 Create football match

FR2 Store match details

FR3 Browse matches

FR4 Join request

FR5 Join public match

FR6 Leave match

Sprint 2

FR7 Attendance confirmation

FR8 View participants

FR9 Cancel match

FR10 Waiting list

FR11 Automatic replacement

FR12 Filters

---

## Should Have (FR13 - FR24)

Sprint 3

FR13 Match history

FR14 Notifications

FR15 Invitations

FR16 Invitation links

FR17 Favorite players

FR18 Report users

Sprint 4

FR19 Match recommendations

FR20 Statistics

FR21 Player ratings

FR22 Comments

FR23 Player profile

FR24 Automatic balanced teams

---

## Could Have

FR25 Calendar integration

FR26 Field availability

FR27 Real-time chat

---

## Won't Have

FR28 Payments

FR29 Smartwatch integration

FR30 AI highlights

---

# 11. Sprint Planning

## Sprint 1

Requirements

FR1

FR2

FR3

FR4

FR5

FR6

Goal

Implement the complete basic match management.

---

## Sprint 2

Requirements

FR7

FR8

FR9

FR10

FR11

FR12

Goal

Complete match lifecycle.

---

## Sprint 3

Requirements

FR13

FR14

FR15

FR16

FR17

FR18

Goal

Improve user interaction.

---

## Sprint 4

Requirements

FR19

FR20

FR21

FR22

FR23

FR24

Goal

Intelligent features.

---

# 12. Usability Requirements

UR1

Registration should take less than 5 minutes.

UR2

Search results should appear in less than 4 seconds.

UR3

Critical actions must display confirmation feedback.

UR4

Forms must display validation errors.

UR5

Primary tasks should require no more than five user interactions.

UR6

Navigation must remain consistent throughout the application.

---

# 13. Logical Database Requirements

Current logical model

## User

Stores:

- id
- first_name
- last_name
- email (unique)
- password
- skill_level
- profile_picture (optional)
- created_at

---

## Match

Stores

- id
- organizer_id
- title
- date_time
- location
- skill_level
- max_players
- visibility

---

## MatchParticipant

Stores

- id
- match_id
- player_id
- status
- attendance_confirmed

---

## JoinRequest

Stores

- id
- player_id
- match_id
- request_date
- request_status

---

Integrity Constraints

- One player cannot appear twice in the same match.
- Historical information must be preserved.
- Foreign Keys enforce referential integrity.

---

# 14. Planned Django Architecture

Project

config/

Applications

core/

General pages.

users/

Authentication

Profiles

Player

matches/

Business logic

Models expected

User

Match

MatchParticipant

JoinRequest

Future

Notification

Invitation

Rating

Comment

Statistics

---

# 15. Development Roadmap

Current phase

Beginning implementation.

Recommended implementation order

1. Configure Django

2. Configure GitHub

3. Create apps

4. Design models.py

5. Create migrations

6. Configure Django Admin

7. Insert test data

8. Implement Sprint 1

9. Views

10. Templates

11. Styling

12. Testing

---

# 16. GitHub Organization

Repository

Local-Sports

Recommended structure

README

Wiki

Product Vision

Software Requirements Specification

Sprint Planning

Retrospectives

Weekly Reports

GitHub Issues

One Issue per Functional Requirement

Milestones

Sprint 1

Sprint 2

Sprint 3

Sprint 4

Project Board

Backlog

To Do

In Progress

Review

Done

---

# 17. Weekly Report

Completed

- Designed the initial database structure.
- Defined logical database requirements.
- Collaborated in reviewing the functional requirements.

Plan

- Start Django implementation.
- Design project structure.
- Implement models.
- Create initial page layout.

Issues

No blocking issues.

---

# 18. Retrospective

Continue

- Weekly Scrum meetings.
- Product Backlog updates.
- GitHub Issues.
- Requirement reviews.

Start

- Standardize Django project structure.
- Standardize coding conventions.
- Improve planning before implementation.

Stop

- Delaying commits.
- Developing large features without prior design discussion.

---

# 19. Video

YouTube

https://youtu.be/HVcPBZa7R6A

Content

- Project name
- Problem
- Team members
- Value proposition
- Top 10 Functional Requirements

---

# 20. Current Implementation Status

Repository has been created on GitHub.

Implementation has just started.

Next steps

- Clone repository
- Create Python virtual environment
- Install Django
- Create Django project
- Create apps:
  - core
  - users
  - matches
- Configure settings.py
- Create models.py
- Run migrations
- Configure admin.py
- Create first commit

---

# 21. Important Engineering Decisions

- Authentication is considered a technical requirement.
- Football (soccer) is the only supported sport in the MVP.
- Matchmaking is postponed until after the MVP.
- The project follows Scrum throughout development.
- Functional requirements are prioritized using the MoSCoW method.
- Development is divided into four sprints aligned with the functional requirements.
- SQLite will be used during development; PostgreSQL is planned for production.
- The architecture should remain modular using Django apps.

---

# 22. Coach Notes (Guidelines for Future Development)

When continuing this project in another conversation:

- Act as a Software Engineering coach rather than simply generating code.
- Analyze requirements before proposing solutions.
- Prioritize maintainability, scalability, and clean architecture.
- Justify technical decisions when multiple alternatives exist.
- Follow the project roadmap and sprint planning.
- Before implementing new features, verify that they align with the corresponding sprint requirements.
- Keep consistency between the SRS, database design, Django models, and implementation.
- Use Django best practices (apps, models, migrations, admin, templates, views, URLs, forms, and services where appropriate).
- Avoid implementing future (Should/Could) features before completing the MVP.
