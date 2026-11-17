package com.jarvis.companion.ui.common

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.GenericShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import com.jarvis.companion.ui.theme.*

/** Cantos "chanfrados" estilo HUD: corta diagonais no topo-esquerdo e base-direita. */
fun formaHud(corte: Float = 14f): Shape = GenericShape { size, _ ->
    moveTo(corte, 0f)
    lineTo(size.width, 0f)
    lineTo(size.width, size.height - corte)
    lineTo(size.width - corte, size.height)
    lineTo(0f, size.height)
    lineTo(0f, corte)
    close()
}

/** Painel transparente com borda neon fina — substitui ElevatedCard na tela. */
@Composable
fun HudPanel(
    modifier: Modifier = Modifier,
    corBorda: Color = NucleoAzul.copy(alpha = 0.35f),
    conteudo: @Composable ColumnScope.() -> Unit,
) {
    val forma = remember { formaHud(corte = 18f) }
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(forma)
            .background(SuperficieAlta.copy(alpha = 0.55f))
            .border(1.dp, corBorda, forma)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        content = conteudo,
    )
}

/** Cartao de uma metrica: valor grande, legenda pequena, linha neon embaixo. */
@Composable
fun StatusCard(titulo: String, valor: String, destaque: Color = NucleoAzul) {
    val forma = remember { formaHud(corte = 10f) }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(forma)
            .background(Superficie.copy(alpha = 0.7f))
            .border(1.dp, destaque.copy(alpha = 0.35f), forma)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            titulo,
            style = MaterialTheme.typography.labelSmall.copy(letterSpacing = androidx.compose.ui.unit.TextUnit.Unspecified),
            color = destaque,
        )
        Text(valor, style = MaterialTheme.typography.titleMedium, color = Texto)
        Box(
            Modifier
                .fillMaxWidth()
                .height(1.dp)
                .background(
                    Brush.horizontalGradient(
                        listOf(destaque.copy(alpha = 0.6f), Color.Transparent)
                    )
                ),
        )
    }
}

/**
 * Nucleo animado — anel externo pulsando devagar, anel medio girando sutil,
 * ponto central vivo. Reage a [ativo]: parado fica frio e lento.
 */
@Composable
fun CoreMark(modifier: Modifier = Modifier, ativo: Boolean = true) {
    val transicao = rememberInfiniteTransition(label = "nucleo")
    val pulso by transicao.animateFloat(
        0.85f, 1f,
        infiniteRepeatable(tween(1800, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "pulso",
    )
    val giro by transicao.animateFloat(
        0f, 360f,
        infiniteRepeatable(tween(14000, easing = LinearEasing), RepeatMode.Restart),
        label = "giro",
    )
    val corPrimaria = if (ativo) NucleoAzul else TextoAtenuado
    val corSecundaria = if (ativo) NucleoMagenta else Contorno

    Box(modifier = modifier.size(84.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val r = size.minDimension / 2f
            // halo radial
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(corSecundaria.copy(alpha = 0.35f * pulso), Color.Transparent),
                ),
                radius = r,
            )
            // anel externo
            drawCircle(
                color = corPrimaria.copy(alpha = 0.55f),
                radius = r * 0.92f,
                style = Stroke(width = 1.4f),
            )
            // arco girando (sensacao de "scanning")
            drawArc(
                color = corPrimaria.copy(alpha = 0.85f),
                startAngle = giro,
                sweepAngle = 70f,
                useCenter = false,
                topLeft = Offset(r - r * 0.72f, r - r * 0.72f),
                size = androidx.compose.ui.geometry.Size(r * 1.44f, r * 1.44f),
                style = Stroke(width = 2.2f),
            )
            // ponto central vivo
            drawCircle(color = corPrimaria, radius = r * 0.18f * pulso)
        }
    }
}

/** Chip com ponto pulsante colorido — HUD vivo em vez de texto parado. */
@Composable
fun StatusChip(texto: String, cor: Color) {
    val transicao = rememberInfiniteTransition(label = "chip")
    val alpha by transicao.animateFloat(
        0.35f, 1f,
        infiniteRepeatable(tween(1400, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "a",
    )
    val forma = remember { formaHud(corte = 6f) }
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        modifier = Modifier
            .clip(forma)
            .background(cor.copy(alpha = 0.08f))
            .border(1.dp, cor.copy(alpha = 0.55f), forma)
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Box(
            Modifier
                .size(6.dp)
                .clip(androidx.compose.foundation.shape.CircleShape)
                .background(cor.copy(alpha = alpha)),
        )
        Text(texto, style = MaterialTheme.typography.labelLarge, color = cor)
    }
}

/**
 * Botao de microfone grande e circular, com ondas concentricas quando ativo.
 * ativo=true dispara as ondas; o toque sempre chama [aoTocar].
 */
@Composable
fun MicButton(
    ativo: Boolean,
    modoContinuo: Boolean = false,
    aoTocar: () -> Unit,
) {
    val transicao = rememberInfiniteTransition(label = "mic")
    val onda by transicao.animateFloat(
        0f, 1f,
        infiniteRepeatable(tween(1800, easing = LinearEasing), RepeatMode.Restart),
        label = "onda",
    )
    val corBase = if (modoContinuo) NucleoMagenta else NucleoAzul

    Box(
        modifier = Modifier
            .size(104.dp)
            .clip(androidx.compose.foundation.shape.CircleShape)
            .clickable(onClick = aoTocar),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val r = size.minDimension / 2f
            if (ativo) {
                for (i in 0..2) {
                    val fase = (onda + i * 0.33f) % 1f
                    drawCircle(
                        color = corBase.copy(alpha = (1f - fase) * 0.45f),
                        radius = r * (0.55f + fase * 0.45f),
                        style = Stroke(width = 1.4f),
                    )
                }
            }
            drawCircle(
                color = corBase.copy(alpha = 0.18f),
                radius = r * 0.62f,
            )
            drawCircle(
                color = corBase,
                radius = r * 0.62f,
                style = Stroke(width = 1.6f),
            )
        }
        Icon(
            imageVector = if (modoContinuo) Icons.Filled.MicOff else Icons.Filled.Mic,
            contentDescription = "Microfone",
            tint = corBase,
            modifier = Modifier.size(36.dp),
        )
    }
}

/** Linha neon fina com gradiente — divisor sutil estilo HUD. */
@Composable
fun NeonLine(cor: Color = NucleoAzul.copy(alpha = 0.6f)) {
    Box(
        Modifier
            .fillMaxWidth()
            .height(1.dp)
            .background(
                Brush.horizontalGradient(
                    listOf(Color.Transparent, cor, Color.Transparent),
                ),
            ),
    )
}
