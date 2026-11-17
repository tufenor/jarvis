package com.jarvis.companion.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Sempre escuro: a UI foi desenhada no escuro e perderia a identidade em claro.
// Ainda assim respeitamos o fator de escala de fonte do sistema.
private val Esquema = darkColorScheme(
    primary = NucleoAzul,
    onPrimary = Fundo,
    secondary = NucleoMagenta,
    onSecondary = Fundo,
    tertiary = NucleoAmbar,
    onTertiary = Fundo,
    background = Fundo,
    onBackground = Texto,
    surface = Superficie,
    onSurface = Texto,
    surfaceVariant = SuperficieAlta,
    onSurfaceVariant = TextoSuave,
    outline = Contorno,
    outlineVariant = Contorno,
    error = PerigoVermelho,
    onError = Color.Black,
)

@Composable
fun JarvisTheme(
    @Suppress("UNUSED_PARAMETER") escuro: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(colorScheme = Esquema, typography = JarvisTypography, content = content)
}
