plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.jarvis.companion"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.jarvis.companion"
        minSdk = 24         // cobre o A53 com folga (Android 7+)
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // Le o token do pc_agent de agente/TOKEN.txt (fora da pasta mobile),
        // injeta no APK via BuildConfig. Vazio quando o arquivo nao existe.
        val tokenFile = rootProject.file("../agente/TOKEN.txt")
        val agentToken = if (tokenFile.exists()) tokenFile.readText().trim() else ""
        buildConfigField("String", "PC_AGENT_TOKEN", "\"$agentToken\"")
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            // Release precisa de keystore próprio; configure em ~/.gradle ou
            // via variáveis de ambiente para não deixar segredo no repositório.
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures { compose = true; buildConfig = true }
    packaging {
        resources.excludes += setOf("/META-INF/{AL2.0,LGPL2.1}", "META-INF/NOTICE.md")
        // Vosk vem com libs .so para muitas ABIs; limita ao que o A53 usa.
        jniLibs {
            useLegacyPackaging = true
        }
    }
    testOptions { unitTests { isReturnDefaultValues = true } }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.09.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.19.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.11.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.11.0")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.navigation:navigation-compose:2.10.2")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.compose.ui:ui-tooling-preview")

    // Preferências criptografadas: a chave mestre é guardada no Android Keystore,
    // então o cookie de sessão não vira texto puro no disco.
    implementation("androidx.security:security-crypto:1.1.0")

    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    implementation("com.google.android.gms:play-services-location:21.3.0")

    // Vosk — reconhecimento de voz offline (pt-BR), modelo baixa opt-in.
    // Apache-2.0; JNA necessaria pelo wrapper do Vosk.
    implementation("com.alphacephei:vosk-android:0.3.47@aar")
    implementation("net.java.dev.jna:jna:5.13.0@aar")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")

    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
