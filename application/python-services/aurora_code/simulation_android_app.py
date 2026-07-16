#!/usr/bin/env python3
"""Native Android probe source embedded in the WS12 test APK."""

MANIFEST = '''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="ia.aurora.codeprobe">
  <uses-permission android:name="android.permission.INTERNET" />
  <application android:theme="@android:style/Theme.Material.Light.NoActionBar"
      android:label="Aurora WS12" android:usesCleartextTraffic="true">
    <activity android:name=".MainActivity" android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
      </intent-filter>
    </activity>
  </application>
</manifest>
'''

ACTIVITY_SOURCE = r'''package ia.aurora.codeprobe;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.ViewGroup;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
  private TextView status;
  private String profile;
  private boolean failed;
  private boolean completed;
  private boolean interactionLogged;
  private int loadRetries;

  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    String rawProfile = getIntent().getStringExtra("device_profile");
    profile = rawProfile == null ? "device" : rawProfile;
    LinearLayout root = new LinearLayout(this);
    root.setOrientation(LinearLayout.VERTICAL);
    root.setBackgroundColor(Color.rgb(8, 14, 18));
    root.setOnApplyWindowInsetsListener((view, insets) -> {
      view.setPadding(0, 0, 0, insets.getSystemWindowInsetBottom());
      return insets;
    });
    status = new TextView(this);
    status.setText("WS12 " + profile.toUpperCase() + ": STARTING");
    status.setTextColor(Color.WHITE);
    status.setBackgroundColor(Color.rgb(21, 94, 117));
    status.setTextSize(14);
    status.setMaxLines(3);
    status.setPadding(32, 84, 32, 24);
    root.addView(status, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT));
    WebView web = new WebView(this);
    web.setBackgroundColor(Color.rgb(8, 14, 18));
    web.getSettings().setJavaScriptEnabled(true);
    web.getSettings().setDomStorageEnabled(true);
    web.setWebViewClient(new WebViewClient() {
      @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
        if (!request.isForMainFrame()) return;
        failed = true;
        if (loadRetries++ < 8) {
          status.setText("WS12 " + profile.toUpperCase() + ": NETWORK RETRY " + loadRetries);
          view.postDelayed(() -> { failed = false; view.reload(); }, 2000);
        } else {
          status.setText("AURORA_WS12_PWA_FAILED " + error.getDescription());
        }
      }
      @Override public void onPageFinished(WebView view, String url) {
        if (!failed && !completed) waitForAurora(view, 0);
      }
    });
    root.addView(web, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
    setContentView(root);
    String target = getIntent().getStringExtra("target_url");
    web.loadUrl(target == null ? "about:blank" : target);
  }

  private void waitForAurora(WebView view, int attempt) {
    if (failed || completed) return;
    view.evaluateJavascript(
        "(function(){var b=Array.from(document.querySelectorAll('button')).find(function(x){return /Continuer sans admin/i.test(x.innerText||'')});return (b?'READY':'WAIT')+'|'+document.title+'|'+document.body.innerText.length+'|'+location.host})()",
        value -> {
          if (value != null && value.contains("READY|")) {
            completed = true;
            String marker = "AURORA_WS12_PWA_EXECUTED " + profile + " " + value;
            status.setText("WS12 " + profile.toUpperCase() + ": EXECUTED\nAurora front ready");
            status.setContentDescription(marker);
            Log.i("AuroraWS12", marker);
            waitForInteraction(view, 0);
          } else if (attempt < 90) {
            view.postDelayed(() -> waitForAurora(view, attempt + 1), 500);
          } else {
            failed = true;
            status.setText("AURORA_WS12_PWA_FAILED React readiness timeout");
          }
        });
  }

  private void waitForInteraction(WebView view, int attempt) {
    if (failed || interactionLogged) return;
    view.evaluateJavascript(
        "(function(){var text=document.body.innerText||'';var b=Array.from(document.querySelectorAll('button')).find(function(x){return /Continuer sans admin/i.test(x.innerText||'')});return !b&&/JUAN OF BIKE/i.test(text)})()",
        value -> {
          if ("true".equals(value)) {
            interactionLogged = true;
            String marker = "AURORA_WS12_INTERACTION_VERIFIED " + profile;
            status.setText("WS12 " + profile.toUpperCase() + ": INTERACTION OK\nAurora front ready");
            Log.i("AuroraWS12", marker);
          } else if (attempt < 60) {
            view.postDelayed(() -> waitForInteraction(view, attempt + 1), 500);
          }
        });
  }
}
'''
