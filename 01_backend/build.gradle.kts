plugins {
	kotlin("jvm") version "2.3.21"
	kotlin("plugin.spring") version "2.3.21"
	id("org.springframework.boot") version "4.1.1"
	id("io.spring.dependency-management") version "1.1.7"
}

group = "pe.edu.lcb"
version = "0.0.1-SNAPSHOT"
description = "API de Radar: analisis de anuncios de la competencia"

java {
	toolchain {
		languageVersion = JavaLanguageVersion.of(21)
	}
}

repositories {
	mavenCentral()
}

dependencies {
	implementation("org.springframework.boot:spring-boot-starter-actuator")
	implementation("org.springframework.boot:spring-boot-starter-validation")
	implementation("org.springframework.boot:spring-boot-starter-webmvc")
	implementation("org.springframework.boot:spring-boot-starter-jdbc")
	implementation("org.jetbrains.kotlin:kotlin-reflect")
	implementation("tools.jackson.module:jackson-module-kotlin")
	// Base local del prototipo. Al pasar al motor del anfitrion solo cambian
	// este driver, el dialecto del esquema y la URL de conexion.
	implementation("org.xerial:sqlite-jdbc:3.50.3.0")
	testImplementation("org.springframework.boot:spring-boot-starter-webmvc-test")
	testImplementation("org.jetbrains.kotlin:kotlin-test-junit5")
	testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

kotlin {
	compilerOptions {
		freeCompilerArgs.addAll("-Xjsr305=strict", "-Xannotation-default-target=param-property")
	}
}

// El esquema vive en 04_bd (unica fuente) y se empaqueta como recurso.
tasks.processResources {
	from("../04_bd") {
		include("*.sql")
		into("bd")
	}
}

tasks.withType<Test> {
	useJUnitPlatform()
}
