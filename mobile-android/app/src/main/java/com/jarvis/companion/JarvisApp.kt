package com.jarvis.companion

import android.app.Application
import com.jarvis.companion.core.di.Services

/** Pontos de entrada ao processo: a Application segura o service locator. */
class JarvisApp : Application() {
    lateinit var services: Services
        private set

    override fun onCreate() {
        super.onCreate()
        services = Services.build(this)
    }
}
