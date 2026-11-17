package com.jarvis.companion.ui.common

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.companion.ui.theme.*
import kotlin.math.cos
import kotlin.math.sin

/**
 * Pano de fundo do app: gradiente radial escuro + grid discreto de linhas.
 * Fica fixo atrás de tudo, não interage. Ocupa o container inteiro.
 */
@Composable
fun BackgroundHud(modifier: Modifier = Modifier) {
    Canvas(modifier = modifier.fillMaxSize()) {
        // gradiente radial centralizado que sugere um "core" global
        drawRect(
            brush = Brush.radialGradient(
                colors = listOf(Fundo, FundoProfundo),
                center = Offset(size.width * 0.5f, size.height * 0.28f),
                radius = size.maxDimension * 0.9f,
            ),
            size = size,
        )
        // grid tech bem sutil
        val passo = 32.dp.toPx()
        var x = 0f
        while (x < size.width) {
            drawLine(GridCor, Offset(x, 0f), Offset(x, size.height), strokeWidth = 0.6f)
            x += passo
        }
        var y = 0f
        while (y < size.height) {
            drawLine(GridCor, Offset(0f, y), Offset(size.width, y), strokeWidth = 0.6f)
            y += passo
        }
        // glow azul no topo
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(GlowAzul, Color.Transparent),
                center = Offset(size.width * 0.5f, size.height * 0.1f),
                radius = size.width * 0.9f,
            ),
            radius = size.width * 0.9f,
            center = Offset(size.width * 0.5f, size.height * 0.1f),
        )
    }
}

/**
 * Núcleo "hero" grande no topo. Visual mais marcante que o CoreMark pequeno:
 * dois anéis contra-rotacionando, pétalas de arcos saindo, miolo pulsando.
 */
@Composable
fun HeroNucleo(
    modifier: Modifier = Modifier,
    estado: EstadoNucleo = EstadoNucleo.Repouso,
) {
    val transicao = rememberInfiniteTransition(label = "hero")
    val giroHorario by transicao.animateFloat(
        0f, 360f,
        infiniteRepeatable(tween(18000, easing = LinearEasing), RepeatMode.Restart),
        label = "giroH",
    )
    val giroAntiHorario by transicao.animateFloat(
        360f, 0f,
        infiniteRepeatable(tween(26000, easing = LinearEasing), RepeatMode.Restart),
        label = "giroAH",
    )
    val pulsoLento by transicao.animateFloat(
        0.9f, 1.05f,
        infiniteRepeatable(tween(2600, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "pulsoL",
    )
    val pulsoRapido by transicao.animateFloat(
        0.85f, 1f,
        infiniteRepeatable(tween(900, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "pulsoR",
    )
    val (corA, corB) = estado.cores()
    val velocidadeMult = estado.velocidade()

    Box(modifier = modifier.size(220.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val r = size.minDimension / 2f
            val c = Offset(size.width / 2f, size.height / 2f)

            // halo radial externo
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(corB.copy(alpha = 0.25f * pulsoLento), Color.Transparent),
                    center = c, radius = r * 1.1f,
                ),
                radius = r * 1.1f, center = c,
            )
            // aro externo pontilhado
            val pontos = 60
            for (i in 0 until pontos) {
                val ang = (i * 360f / pontos + giroHorario * velocidadeMult) * (Math.PI / 180f).toFloat()
                val raio = r * 0.95f
                val pos = Offset(c.x + cos(ang) * raio, c.y + sin(ang) * raio)
                drawCircle(corA.copy(alpha = 0.6f), radius = 1.1f, center = pos)
            }
            // anel medio continuo
            drawCircle(
                color = corA.copy(alpha = 0.55f),
                radius = r * 0.78f,
                center = c,
                style = Stroke(width = 1.2f),
            )
            // arco scanning principal
            drawArc(
                color = corA,
                startAngle = giroHorario * velocidadeMult,
                sweepAngle = 85f,
                useCenter = false,
                topLeft = Offset(c.x - r * 0.78f, c.y - r * 0.78f),
                size = Size(r * 1.56f, r * 1.56f),
                style = Stroke(width = 2.6f),
            )
            // arco scanning secundario, contra-rotacionando
            drawArc(
                color = corB.copy(alpha = 0.8f),
                startAngle = giroAntiHorario * velocidadeMult,
                sweepAngle = 45f,
                useCenter = false,
                topLeft = Offset(c.x - r * 0.62f, c.y - r * 0.62f),
                size = Size(r * 1.24f, r * 1.24f),
                style = Stroke(width = 1.6f),
            )
            // petalas de arcos
            val petalas = 6
            for (i in 0 until petalas) {
                val ang = i * (360f / petalas) + giroAntiHorario * 0.3f * velocidadeMult
                drawArc(
                    color = corA.copy(alpha = 0.35f),
                    startAngle = ang,
                    sweepAngle = 18f,
                    useCenter = false,
                    topLeft = Offset(c.x - r * 0.48f, c.y - r * 0.48f),
                    size = Size(r * 0.96f, r * 0.96f),
                    style = Stroke(width = 1.4f),
                )
            }
            // miolo preenchido pulsando
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(corA, corB.copy(alpha = 0.55f), Color.Transparent),
                    center = c, radius = r * 0.32f * pulsoRapido,
                ),
                radius = r * 0.32f * pulsoRapido,
                center = c,
            )
            drawCircle(corA, radius = r * 0.09f * pulsoRapido, center = c)
        }
    }
}

enum class EstadoNucleo {
    Repouso, Escutando, Pensando, Respondendo, Alerta, Offline;

    fun cores(): Pair<Color, Color> = when (this) {
        Repouso -> NucleoAzul to NucleoMagenta
        Escutando -> NucleoAzul to NucleoAzul
        Pensando -> NucleoAmbar to NucleoMagenta
        Respondendo -> NucleoMagenta to NucleoAzul
        Alerta -> PerigoVermelho to NucleoAmbar
        Offline -> TextoAtenuado to Contorno
    }

    fun velocidade(): Float = when (this) {
        Escutando -> 2.2f
        Pensando -> 2.8f
        Respondendo -> 1.8f
        Alerta -> 3.5f
        Offline -> 0.15f
        Repouso -> 1f
    }
}

/**
 * Tile quadrado de ação rápida: ícone grande, label mono curto, cor de destaque.
 * Encaixa em grade 2 ou 3 colunas. Desabilita com [habilitado]=false.
 */
@Composable
fun ActionTile(
    icone: ImageVector,
    titulo: String,
    cor: Color = NucleoAzul,
    habilitado: Boolean = true,
    perigoso: Boolean = false,
    aoTocar: () -> Unit,
) {
    val borda = when {
        !habilitado -> Contorno
        perigoso -> PerigoVermelho.copy(alpha = 0.6f)
        else -> cor.copy(alpha = 0.55f)
    }
    val tonel = if (habilitado) cor else TextoAtenuado
    val forma = RoundedCornerShape(14.dp)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .aspectRatio(1.05f)
            .clip(forma)
            .background(SuperficieVidro)
            .border(1.dp, borda, forma)
            .clickable(enabled = habilitado, onClick = aoTocar)
            .padding(12.dp),
        verticalArrangement = Arrangement.SpaceBetween,
    ) {
        Icon(icone, contentDescription = titulo, tint = tonel, modifier = Modifier.size(28.dp))
        Column {
            Text(
                titulo.uppercase(),
                style = MaterialTheme.typography.labelLarge.copy(
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.SemiBold,
                    letterSpacing = 1.5.sp,
                ),
                color = tonel,
            )
            Spacer(Modifier.height(4.dp))
            Box(
                Modifier
                    .fillMaxWidth()
                    .height(2.dp)
                    .background(
                        Brush.horizontalGradient(
                            listOf(tonel.copy(alpha = 0.7f), Color.Transparent)
                        )
                    ),
            )
        }
    }
}

/** Cartao vidro arredondado — usar em blocos secundarios da nova tela. */
@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    corBorda: Color = ContornoNeon,
    conteudo: @Composable ColumnScope.() -> Unit,
) {
    val forma = RoundedCornerShape(16.dp)
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(forma)
            .background(SuperficieVidro)
            .border(1.dp, corBorda.copy(alpha = 0.6f), forma)
            .padding(16.dp),
        content = conteudo,
    )
}

/**
 * Quatro "micro-metricas" lado a lado: PC / PLACA / TEMP / UMIDADE.
 * Mais compacto que GradeStatus; tudo cabe numa linha no A53.
 */
@Composable
fun MicroMetrica(label: String, valor: String, cor: Color, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(10.dp))
            .background(Superficie.copy(alpha = 0.55f))
            .border(1.dp, cor.copy(alpha = 0.3f), RoundedCornerShape(10.dp))
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            label,
            style = MaterialTheme.typography.labelMedium.copy(
                fontFamily = FontFamily.Monospace, letterSpacing = 1.sp, fontSize = 9.sp,
            ),
            color = cor,
        )
        Text(
            valor,
            style = MaterialTheme.typography.titleMedium.copy(
                fontFamily = FontFamily.Monospace, fontSize = 14.sp,
            ),
            color = Texto,
        )
    }
}

/** Botao de microfone "hero" — 140dp, estilo FAB cyberpunk com anéis. */
@Composable
fun MicHero(
    ativo: Boolean,
    modoContinuo: Boolean,
    aoTocar: () -> Unit,
) {
    val transicao = rememberInfiniteTransition(label = "micHero")
    val onda by transicao.animateFloat(
        0f, 1f,
        infiniteRepeatable(tween(1600, easing = LinearEasing), RepeatMode.Restart),
        label = "onda",
    )
    val corBase = if (modoContinuo) NucleoMagenta else NucleoAzul
    Box(
        modifier = Modifier
            .size(140.dp)
            .clip(CircleShape)
            .clickable(onClick = aoTocar),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val r = size.minDimension / 2f
            // halo radial
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(corBase.copy(alpha = 0.35f), Color.Transparent),
                ),
                radius = r,
            )
            if (ativo) {
                for (i in 0..2) {
                    val fase = (onda + i * 0.33f) % 1f
                    drawCircle(
                        color = corBase.copy(alpha = (1f - fase) * 0.55f),
                        radius = r * (0.6f + fase * 0.4f),
                        style = Stroke(width = 1.8f),
                    )
                }
            }
            drawCircle(color = corBase.copy(alpha = 0.22f), radius = r * 0.68f)
            drawCircle(color = corBase, radius = r * 0.68f, style = Stroke(width = 2f))
        }
        Icon(
            imageVector = Icons.Filled.Mic,
            contentDescription = "Microfone",
            tint = corBase,
            modifier = Modifier.size(48.dp),
        )
    }
}

/** Saudacao dinamica ao operador: "BOM DIA / BOA TARDE / BOA NOITE, [NOME]". */
fun saudacao(operador: String, horaHoje: Int): String {
    val periodo = when (horaHoje) {
        in 5..11 -> "BOM DIA"
        in 12..17 -> "BOA TARDE"
        in 18..23 -> "BOA NOITE"
        else -> "BOA MADRUGADA"
    }
    return "$periodo, ${operador.uppercase()}"
}
