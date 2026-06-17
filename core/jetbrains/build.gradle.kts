plugins {
    id("buildsrc.convention.kotlin-jvm")
    id("org.jetbrains.intellij.platform") version "2.5.0"
}

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

dependencies {
    intellijPlatform {
        intellijIdeaCommunity("2024.3")
    }
    testImplementation("org.junit.jupiter:junit-jupiter:5.11.4")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
    testRuntimeOnly("junit:junit:4.13.2")
}

intellijPlatform {
    pluginConfiguration {
        id = "org.solfadoc.jetbrains"
        name = "Solfadoc"
        version = "0.1.0"
        description = "Syntax highlighting for solfadoc notation files"
        vendor {
            name = "solfadoc"
        }
    }
    buildSearchableOptions = false
}
