"""Capture existing native views with the dedicated review account on an iPhone simulator.

The Swift helper is injected only into the temporary CI checkout's test target.
It does not change, archive, sign, or upload the release app. No synthetic UI is used.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

root = Path.cwd()
source = root / "private-source"
temporary = Path(os.environ["RUNNER_TEMP"])
account = json.loads(os.environ["REVIEW_JSON"])
log = (temporary / "store-capture.log").open("w")

def run(args, cwd=source):
    subprocess.run(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)

swift = r'''
import XCTest
import SwiftUI
import UIKit
@testable import Zai

private actor StoreCaptureVault: CredentialStoring {
    private var values: [String: Data] = [:]
    func read(_ key: String) -> Data? { values[key] }
    func write(_ data: Data, key: String) { values[key] = data }
    func remove(_ key: String) { values.removeValue(forKey: key) }
}

@MainActor
final class StoreCaptureTests: XCTestCase {
    private var captureWindow: UIWindow?
    private var captureSession: ZaiSession!
    private let loading = AppLoadingGate()
    private let language = AppLanguageChoice()

    func testCaptureStoreScreens() async throws {
        let env = ProcessInfo.processInfo.environment
        captureSession = ZaiSession(vault: StoreCaptureVault())
        try await captureSession.login(account: try XCTUnwrap(env["STORE_REVIEW_ACCOUNT"]), password: try XCTUnwrap(env["STORE_REVIEW_PASSWORD"]))
        XCTAssertTrue(captureSession.isAuthenticated)
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let window = UIWindow(windowScene: scene)
        window.frame = scene.coordinateSpace.bounds
        window.windowLevel = .normal + 1
        captureWindow = window
        loading.logoPlayed(); loading.restoreSettled(); loading.pageReady()
        for choice in [AppLanguage.en, AppLanguage.zh] {
            language.language = choice
            let locale = choice == .en ? "en-US" : "zh-Hans"
            try await capture(AuthenticatedZaiRoot(session: captureSession), name: locale + "-01-conversation", wait: 18)
            try await capture(CompanionPickView(session: captureSession, guest: false), name: locale + "-02-companions", wait: 12)
            try await capture(NavigationStack { VoiceFeatureView(session: captureSession, audio: NativeAudioController()) }, name: locale + "-03-voices", wait: 10)
            try await capture(NavigationStack { PrivacyFeatureView(session: captureSession, onStartedOver: {}) }, name: locale + "-04-privacy", wait: 8)
        }
        captureWindow?.isHidden = true
        captureWindow = nil
        await captureSession.logout()
    }

    private func capture<V: View>(_ view: V, name: String, wait: UInt64) async throws {
        let window = try XCTUnwrap(captureWindow)
        let root = view.environmentObject(captureSession).environmentObject(loading).environmentObject(language)
            .environment(\.locale, language.language.locale).environment(\.scenePhase, .active)
            .tint(Color(red: 0.39, green: 0.34, blue: 0.94))
        let controller = UIHostingController(rootView: root)
        window.rootViewController = controller
        window.makeKeyAndVisible()
        try await Task.sleep(nanoseconds: wait * 1_000_000_000)
        window.layoutIfNeeded()
        let format = UIGraphicsImageRendererFormat()
        format.scale = window.screen.scale
        format.opaque = true
        let image = UIGraphicsImageRenderer(bounds: window.bounds, format: format).image { _ in
            window.drawHierarchy(in: window.bounds, afterScreenUpdates: true)
        }
        let folder = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("StoreScreenshots", isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        try XCTUnwrap(image.pngData()).write(to: folder.appendingPathComponent(name + ".png"))
    }
}
'''

try:
    run(["python3", "scripts/fetch-bundled-looks.py"])
    (source / "ios/NativeZaiTests/StoreCaptureTests.swift").write_text(swift)
    run(["python3", "scripts/generate-native-project.py"])
    scheme_path = source / "ios/NativeZai.xcodeproj/xcshareddata/xcschemes/Zai.xcscheme"
    tree = ET.parse(scheme_path)
    test_action = tree.getroot().find("TestAction")
    test_action.set("shouldUseLaunchSchemeArgsEnv", "NO")
    variables = ET.SubElement(test_action, "EnvironmentVariables")
    for key, value in {"STORE_REVIEW_ACCOUNT": account["account"], "STORE_REVIEW_PASSWORD": account["password"]}.items():
        ET.SubElement(variables, "EnvironmentVariable", key=key, value=value, isEnabled="YES")
    tree.write(scheme_path, encoding="utf-8", xml_declaration=True)
    devices = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"]))["devices"]
    candidates = [device for group in devices.values() for device in group if "Pro Max" in device["name"]]
    selected = next((d for d in candidates if d["name"] == "iPhone 17 Pro Max"), candidates[0])
    device = selected["udid"]
    run(["xcrun", "simctl", "bootstatus", device, "-b"])
    run(["xcrun", "simctl", "status_bar", device, "override", "--time", "9:41", "--batteryState", "charged", "--batteryLevel", "100"])
    print("Capturing the released native UI on " + selected["name"], flush=True)
    run(["xcodebuild", "-quiet", "test", "-project", "ios/NativeZai.xcodeproj", "-scheme", "Zai", "-configuration", "Debug",
         "-destination", "platform=iOS Simulator,id=" + device, "-derivedDataPath", str(temporary / "store-derived"),
         "-parallel-testing-enabled", "NO", "-only-testing:NativeZaiTests/StoreCaptureTests", "-test-timeouts-enabled", "YES",
         "-default-test-execution-time-allowance", "240", "-maximum-test-execution-time-allowance", "300",
         "ONLY_ACTIVE_ARCH=YES", "CODE_SIGNING_ALLOWED=NO", "CODE_SIGNING_REQUIRED=NO"])
    container = Path(subprocess.check_output(["xcrun", "simctl", "get_app_container", device, "com.ourzai.app", "data"], text=True).strip())
    screenshots = sorted((container / "Documents/StoreScreenshots").glob("*.png"))
    assert len(screenshots) == 8, "Capture did not return all eight screenshots"
    destination = root / "store-screenshots"
    destination.mkdir(exist_ok=True)
    for screenshot in screenshots:
        shutil.copy2(screenshot, destination / screenshot.name)
    print("Captured eight native screenshots; release app unchanged.", flush=True)
finally:
    log.close()
