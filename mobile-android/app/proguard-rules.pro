# kotlinx.serialization — mantém campos @Serializable em release.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
-keep,includedescriptorclasses class com.jarvis.companion.**$$serializer { *; }
-keepclassmembers class com.jarvis.companion.** {
    *** Companion;
}
-keepclasseswithmembers class com.jarvis.companion.** {
    kotlinx.serialization.KSerializer serializer(...);
}
# OkHttp reflete sobre a classe do TLS; manter o que ele precisa.
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
