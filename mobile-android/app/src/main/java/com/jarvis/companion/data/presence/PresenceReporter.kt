package com.jarvis.companion.data.presence

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import com.google.android.gms.location.CurrentLocationRequest
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.jarvis.companion.data.network.JarvisApi
import com.jarvis.companion.data.network.PresencaRequest
import com.jarvis.companion.data.settings.SettingsStore
import kotlinx.coroutines.CancellableContinuation
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

/**
 * Presença sob demanda — só pede GPS quando o usuário aperta "verificar".
 * Se a permissão não foi concedida, manda presença indeterminada (sem
 * coordenadas), para o JARVIS ao menos saber que o aparelho está ao alcance.
 */
class PresenceReporter(
    private val context: Context,
    private val api: JarvisApi,
    private val settings: SettingsStore,
) {
    suspend fun reportar(evento: String): Resultado {
        val pedido = PresencaRequest(
            presente = null, origem = settings.current().deviceName,
            evento = evento,
        )
        val comGps = if (temPermissao()) obterCoordenada() else null
        val carga = if (comGps != null) pedido.copy(
            presente = true, latitude = comGps.latitude,
            longitude = comGps.longitude, precisaoM = comGps.precisao,
        ) else pedido
        return try {
            api.presenca(carga); Resultado.Enviado(temGps = comGps != null)
        } catch (e: Throwable) { Resultado.Erro(e.message ?: "falha") }
    }

    fun temPermissao(): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) ==
                PackageManager.PERMISSION_GRANTED

    private suspend fun obterCoordenada(): Coord? {
        if (!temPermissao()) return null
        val cliente = LocationServices.getFusedLocationProviderClient(context)
        val pedido = CurrentLocationRequest.Builder()
            .setPriority(Priority.PRIORITY_BALANCED_POWER_ACCURACY)
            .setMaxUpdateAgeMillis(15 * 60 * 1000)
            .build()
        return try {
            suspendCancellableCoroutine { cont: CancellableContinuation<Coord?> ->
                cliente.getCurrentLocation(pedido, null)
                    .addOnSuccessListener { loc ->
                        if (loc == null) cont.resume(null)
                        else cont.resume(Coord(loc.latitude, loc.longitude, loc.accuracy))
                    }
                    .addOnFailureListener { cont.resume(null) }
            }
        } catch (_: SecurityException) { null }
    }

    data class Coord(val latitude: Double, val longitude: Double, val precisao: Float)
    sealed interface Resultado {
        data class Enviado(val temGps: Boolean) : Resultado
        data class Erro(val mensagem: String) : Resultado
    }
}
