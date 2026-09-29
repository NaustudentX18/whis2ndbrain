import 'package:flutter_test/flutter_test.dart';
import 'package:whis_app/api/api_client.dart';

void main() {
  group('Note model tests', () {
    test('fromJson parses Note with full fields', () {
      final json = {
        'capture_id': 'cap-101',
        'status': 'transcribed',
        'transcript': 'Hello world testing voice capture',
        'transcript_source': 'model',
        'received_at': '2026-09-27T08:00:00Z',
        'audio_purged_at': null,
        'category': 'thought',
        'urgency': 'normal',
        'actionable': false,
      };

      final note = Note.fromJson(json);

      expect(note.captureId, 'cap-101');
      expect(note.status, 'transcribed');
      expect(note.transcript, 'Hello world testing voice capture');
      expect(note.transcriptSource, 'model');
      expect(note.hasAudio, isTrue);
      expect(note.isOwnerCorrected, isFalse);
      expect(note.isTranscribed, isTrue);
      expect(note.category, 'thought');
      expect(note.urgency, 'normal');
      expect(note.actionable, isFalse);
    });

    test('hasAudio is false when audio_purged_at is present', () {
      final json = {
        'capture_id': 'cap-102',
        'status': 'reviewed',
        'transcript': 'Purged note audio test',
        'transcript_source': 'owner',
        'received_at': '2026-09-20T08:00:00Z',
        'audio_purged_at': '2026-09-27T08:00:00Z',
        'category': 'todo',
        'urgency': 'high',
        'actionable': true,
      };

      final note = Note.fromJson(json);

      expect(note.hasAudio, isFalse);
      expect(note.isOwnerCorrected, isTrue);
      expect(note.actionable, isTrue);
    });

    test('NotesPage parses page with items and total', () {
      final json = {
        'items': [
          {
            'capture_id': 'cap-1',
            'status': 'received',
            'transcript': null,
            'transcript_source': null,
            'received_at': '2026-09-27T08:00:00Z',
            'audio_purged_at': null,
            'category': null,
            'urgency': null,
            'actionable': null,
          }
        ],
        'total': 1,
        'limit': 50,
        'offset': 0,
      };

      final page = NotesPage.fromJson(json);

      expect(page.items.length, 1);
      expect(page.items.first.captureId, 'cap-1');
      expect(page.total, 1);
      expect(page.hasMore, isFalse);
    });
  });

  group('ApiClient helper tests', () {
    test('audioUrl targets the byte-range API route with no token in the URL', () {
      const client = ApiClient(baseUrl: 'https://omarchy.tail9760ad.ts.net:8765', token: 'secret-token-xyz');
      final url = client.audioUrl('cap-abc-123');

      expect(url, 'https://omarchy.tail9760ad.ts.net:8765/api/v1/notes/cap-abc-123/audio');
      expect(url.contains('token'), isFalse);
      expect(client.audioHeaders['Authorization'], 'Bearer secret-token-xyz');
    });

    test('Note parses tombstone + revision fields', () {
      final note = Note.fromJson({
        'capture_id': 'cap-9',
        'status': 'reviewed',
        'transcript': null,
        'transcript_source': null,
        'received_at': null,
        'audio_purged_at': null,
        'category': null,
        'urgency': null,
        'actionable': null,
        'deleted_at': '2026-09-29T09:00:00Z',
        'revision': 4,
      });

      expect(note.isDeleted, isTrue);
      expect(note.revision, 4);
    });

    test('Note tolerates hosts that omit tombstone/revision fields', () {
      final note = Note.fromJson({
        'capture_id': 'cap-10',
        'status': 'received',
      });

      expect(note.isDeleted, isFalse);
      expect(note.revision, 0);
    });

    test('NotesPage parses next_cursor and reports hasMore from it', () {
      final page = NotesPage.fromJson({
        'items': [],
        'total': 120,
        'limit': 100,
        'offset': 0,
        'next_cursor': 'cap-100',
      });

      expect(page.nextCursor, 'cap-100');
      expect(page.hasMore, isTrue);
    });

    test('NotesPage without cursor falls back to offset arithmetic', () {
      final page = NotesPage.fromJson({
        'items': [],
        'total': 3,
        'limit': 100,
        'offset': 0,
      });

      expect(page.nextCursor, isNull);
      expect(page.hasMore, isFalse);
    });
  });
}
