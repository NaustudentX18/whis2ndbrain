import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Manages host URL and owner token, persisted securely.
///
/// - Token → flutter_secure_storage (Android Keystore-backed AES-256)
/// - Host URL → SharedPreferences (non-secret, no PII)
class AuthStore {
  static const _tokenKey = 'whis_owner_token';
  static const _hostKey = 'whis_host_url';

  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(
      encryptedSharedPreferences: true,
      keyCipherAlgorithm:
          KeyCipherAlgorithm.RSA_ECB_OAEPwithSHA_256andMGF1Padding,
      storageCipherAlgorithm: StorageCipherAlgorithm.AES_GCM_NoPadding,
    ),
  );

  static Future<String?> getToken() async {
    return _storage.read(key: _tokenKey);
  }

  static Future<void> setToken(String token) async {
    await _storage.write(key: _tokenKey, value: token);
  }

  static Future<void> clearToken() async {
    await _storage.delete(key: _tokenKey);
  }

  static Future<String?> getHostUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_hostKey);
  }

  static Future<void> setHostUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_hostKey, url);
  }

  static Future<bool> isConfigured() async {
    final token = await getToken();
    final host = await getHostUrl();
    return token != null &&
        token.isNotEmpty &&
        host != null &&
        host.isNotEmpty;
  }

  static Future<void> clear() async {
    await clearToken();
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_hostKey);
  }
}
