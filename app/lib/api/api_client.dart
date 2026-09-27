import 'dart:convert';
import 'package:http/http.dart' as http;

/// Client for the Whis2ndBrain review server API.
///
/// All requests are authenticated with a Bearer token stored in
/// flutter_secure_storage. The client throws [ApiException] for all
/// non-2xx responses so callers can handle them uniformly.
class ApiClient {
  final String baseUrl; // e.g. "http://100.x.x.x:8765"
  final String token;

  const ApiClient({required this.baseUrl, required this.token});

  Map<String, String> get _headers => {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  Uri _uri(String path, [Map<String, String>? query]) {
    final base = Uri.parse(baseUrl);
    return base.replace(
      path: path,
      queryParameters: query,
    );
  }

  Future<Map<String, dynamic>> _get(String path,
      [Map<String, String>? query]) async {
    final resp = await http.get(_uri(path, query), headers: _headers);
    return _parse(resp);
  }

  Future<Map<String, dynamic>> _patch(String path, Map<String, dynamic> body) async {
    final resp = await http.patch(
      _uri(path),
      headers: _headers,
      body: jsonEncode(body),
    );
    return _parse(resp);
  }

  Future<Map<String, dynamic>> _post(String path,
      [Map<String, dynamic>? body]) async {
    final resp = await http.post(
      _uri(path),
      headers: _headers,
      body: body != null ? jsonEncode(body) : null,
    );
    return _parse(resp);
  }

  Map<String, dynamic> _parse(http.Response resp) {
    if (resp.statusCode >= 200 && resp.statusCode < 300) {
      if (resp.body.isEmpty) return {};
      return jsonDecode(resp.body) as Map<String, dynamic>;
    }
    String message;
    try {
      message = (jsonDecode(resp.body) as Map)['error'] as String? ??
          resp.body;
    } catch (_) {
      message = resp.body;
    }
    throw ApiException(resp.statusCode, message);
  }

  // ── Health ────────────────────────────────────────────────────────────────

  Future<bool> isReady() async {
    try {
      final data = await _get('/api/v1/health/ready');
      return data['status'] == 'ready';
    } catch (_) {
      return false;
    }
  }

  // ── Notes ─────────────────────────────────────────────────────────────────

  Future<NotesPage> listNotes({
    String? status,
    String? search,
    int limit = 50,
    int offset = 0,
  }) async {
    final query = <String, String>{
      'limit': '$limit',
      'offset': '$offset',
      if (status != null) 'status': status,
      if (search != null && search.isNotEmpty) 'search': search,
    };
    final data = await _get('/api/v1/notes', query);
    return NotesPage.fromJson(data);
  }

  Future<Note> getNote(String captureId) async {
    final data = await _get('/api/v1/notes/$captureId');
    return Note.fromJson(data);
  }

  Future<Note> patchNote(String captureId, Map<String, dynamic> patch) async {
    final data = await _patch('/api/v1/notes/$captureId', patch);
    return Note.fromJson(data);
  }

  // ── Settings ──────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getSettings() => _get('/api/v1/settings');

  Future<Map<String, dynamic>> patchSettings(Map<String, dynamic> updates) =>
      _patch('/api/v1/settings', updates);

  // ── Telemetry ─────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getTelemetry() =>
      _get('/api/v1/device/telemetry');

  Future<Map<String, dynamic>> sendHeartbeat(
          [Map<String, dynamic>? data]) =>
      _post('/api/v1/device/heartbeat', data);

  // ── Audio (local streaming — returns the URL for just_audio) ─────────────

  String audioUrl(String captureId) =>
      '$baseUrl/n/$captureId/audio?token=${Uri.encodeComponent(token)}';
}

// ── Models ────────────────────────────────────────────────────────────────────

class Note {
  final String captureId;
  final String status;
  final String? transcript;
  final String? transcriptSource;
  final String? receivedAt;
  final String? audioPurgedAt;
  final String? category;
  final String? urgency;
  final bool? actionable;

  const Note({
    required this.captureId,
    required this.status,
    this.transcript,
    this.transcriptSource,
    this.receivedAt,
    this.audioPurgedAt,
    this.category,
    this.urgency,
    this.actionable,
  });

  factory Note.fromJson(Map<String, dynamic> j) => Note(
        captureId: j['capture_id'] as String,
        status: j['status'] as String,
        transcript: j['transcript'] as String?,
        transcriptSource: j['transcript_source'] as String?,
        receivedAt: j['received_at'] as String?,
        audioPurgedAt: j['audio_purged_at'] as String?,
        category: j['category'] as String?,
        urgency: j['urgency'] as String?,
        actionable: j['actionable'] as bool?,
      );

  bool get hasAudio => audioPurgedAt == null;
  bool get isOwnerCorrected => transcriptSource == 'owner';
  bool get isTranscribed =>
      status == 'transcribed' || status == 'reviewed';
}

class NotesPage {
  final List<Note> items;
  final int total;
  final int limit;
  final int offset;

  const NotesPage(
      {required this.items,
      required this.total,
      required this.limit,
      required this.offset});

  factory NotesPage.fromJson(Map<String, dynamic> j) => NotesPage(
        items: (j['items'] as List)
            .map((e) => Note.fromJson(e as Map<String, dynamic>))
            .toList(),
        total: j['total'] as int,
        limit: j['limit'] as int,
        offset: j['offset'] as int,
      );

  bool get hasMore => offset + items.length < total;
}

// ── Exception ─────────────────────────────────────────────────────────────────

class ApiException implements Exception {
  final int statusCode;
  final String message;

  const ApiException(this.statusCode, this.message);

  @override
  String toString() => 'ApiException($statusCode): $message';
}
