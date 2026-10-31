# The page calls the bridge by method name (window.TripAtlasApp.accounts() …)
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
