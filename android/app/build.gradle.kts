import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

// Release signing comes from local.properties (never committed): RELEASE_STORE_FILE, RELEASE_STORE_PASSWORD,
// RELEASE_KEY_ALIAS, RELEASE_KEY_PASSWORD. Without them the release build is signed with the debug key.
val local = Properties().apply { rootProject.file("local.properties").takeIf { it.exists() }?.inputStream()?.use(::load) }

android {
    namespace = "de.korte_daniel.tripatlas"
    compileSdk = 36

    defaultConfig {
        applicationId = "de.korte_daniel.tripatlas"
        minSdk = 29
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
    }

    signingConfigs {
        if (local.getProperty("RELEASE_STORE_FILE") != null) create("release") {
            storeFile = file(local.getProperty("RELEASE_STORE_FILE"))
            storePassword = local.getProperty("RELEASE_STORE_PASSWORD")
            keyAlias = local.getProperty("RELEASE_KEY_ALIAS")
            keyPassword = local.getProperty("RELEASE_KEY_PASSWORD")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
        debug {
            applicationIdSuffix = ".debug"
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures { compose = true }
    testOptions { unitTests.isReturnDefaultValues = true }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(libs.core.ktx)
    implementation(libs.activity.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.foundation)
    implementation(libs.compose.material3)
    // Saved accounts behind the fingerprint (AccountVault)
    implementation(libs.biometric)
    // biometric pulls in fragment 1.2.5, which rejects the large request codes of the Activity Result API (the file
    // picker for imports) with an IllegalArgumentException -- so a current version, explicitly.
    implementation(libs.fragment.ktx)

    testImplementation(libs.junit)
}
