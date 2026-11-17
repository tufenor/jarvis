package com.jarvis.companion

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.jarvis.companion.ui.auth.LoginScreen
import com.jarvis.companion.ui.theme.JarvisTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Smoke test: a tela de login desenha os textos esperados. */
@RunWith(AndroidJUnit4::class)
class MainScreenUiTest {
    @get:Rule val regra = createComposeRule()

    @Test fun login_mostra_titulo_e_botao() {
        val ctx = androidx.test.core.app.ApplicationProvider.getApplicationContext<JarvisApp>()
        regra.setContent {
            JarvisTheme {
                LoginScreen(services = ctx.services, aoEntrar = {}, abrirServidor = {})
            }
        }
        regra.onNodeWithText("J.A.R.V.I.S.").assertIsDisplayed()
        regra.onNodeWithText("ENTRAR").assertIsDisplayed()
    }
}
