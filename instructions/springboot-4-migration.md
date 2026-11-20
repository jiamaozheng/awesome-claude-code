---
description: "Comprehensive guide for migrating Spring Boot applications from 3.x to 4.0, focusing on Gradle Kotlin DSL and version catalogs"
paths: "**/*.java, **/*.kt, **/build.gradle.kts, **/build.gradle, **/settings.gradle.kts, **/gradle/libs.versions.toml, **/*.properties, **/*.yml, **/*.yaml"
---

# Spring Boot 4.0 Migration

Apply this only when the user explicitly asks to migrate Spring Boot 3.x to 4 (or to fix failures caused by that migration). Editing the Boot version in a build file is not enough. Patch bumps within 3.x and 4.0 to 4.1 upgrades are not covered; follow the target Spring Boot version's [release notes](https://github.com/spring-projects/spring-boot/releases) and [upgrade guide](https://docs.spring.io/spring-boot/upgrading.html) for those, not the JDK-focused `java-upgrade` skill.

For a 3.x to 4 migration, use the `spring-boot-4-migration` skill. It holds the full workflow and topic references (starters, Jackson 3, testing, configuration properties, removed APIs) for Maven and Gradle.

- Detect the current Boot version first and migrate to the latest 3.5.x before moving to 4.0.
- Run the build and tests after each migration step.
- Never read or print secrets such as `.env` files.

Get the skill from this repository: https://github.com/github/awesome-copilot/tree/main/skills/spring-boot-4-migration (install it with the GitHub Copilot CLI plugin marketplace or copy the folder to `.github/skills/spring-boot-4-migration`).