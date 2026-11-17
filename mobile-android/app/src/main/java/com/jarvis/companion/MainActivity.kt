package com.jarvis.companion

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.jarvis.companion.ui.nav.AppNav
import com.jarvis.companion.ui.theme.JarvisTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val services = (application as JarvisApp).services
        setContent {
            JarvisTheme {
                Surface(modifier = Modifier) {
                    AppNav(services = services)
                }
            }
        }
    }
}
