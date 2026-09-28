import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import '../api/api_client.dart';

class NotesScreen extends StatefulWidget {
  final ApiClient client;

  const NotesScreen({super.key, required this.client});

  @override
  State<NotesScreen> createState() => _NotesScreenState();
}

class _NotesScreenState extends State<NotesScreen> {
  final TextEditingController _searchController = TextEditingController();
  List<Note> _notes = [];
  bool _isLoading = false;
  String? _errorMessage;
  String? _selectedFilter; // null = all, or status value

  @override
  void initState() {
    super.initState();
    _loadNotes();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadNotes() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await widget.client.listNotes(
        status: _selectedFilter,
        search: _searchController.text.trim().isEmpty ? null : _searchController.text.trim(),
        limit: 100,
      );
      setState(() {
        _notes = res.items;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to load notes: $e';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  void _openNoteDetail(Note note) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => _NoteDetailSheet(
        note: note,
        client: widget.client,
        onUpdated: _loadNotes,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Voice Notes'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isLoading ? null : _loadNotes,
          ),
        ],
      ),
      body: Column(
        children: [
          // Search & Filter header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search transcripts...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          _loadNotes();
                        },
                      )
                    : null,
              ),
              onSubmitted: (_) => _loadNotes(),
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                _filterChip('All', null),
                const SizedBox(width: 8),
                _filterChip('Transcribed', 'transcribed'),
                const SizedBox(width: 8),
                _filterChip('Reviewed', 'reviewed'),
                const SizedBox(width: 8),
                _filterChip('Received', 'received'),
                const SizedBox(width: 8),
                _filterChip('Unreviewed', 'unreviewed'),
              ],
            ),
          ),
          const Divider(height: 16),
          // Content
          Expanded(
            child: RefreshIndicator(
              onRefresh: _loadNotes,
              child: _buildBody(cs),
            ),
          ),
        ],
      ),
    );
  }

  Widget _filterChip(String label, String? value) {
    final isSelected = _selectedFilter == value;
    return ChoiceChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (selected) {
        setState(() {
          _selectedFilter = selected ? value : null;
        });
        _loadNotes();
      },
    );
  }

  Widget _buildBody(ColorScheme cs) {
    if (_isLoading && _notes.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMessage != null && _notes.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.error_outline, size: 48, color: cs.error),
              const SizedBox(height: 12),
              Text(_errorMessage!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _loadNotes,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_notes.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.mic_none, size: 48, color: Colors.grey),
            SizedBox(height: 12),
            Text(
              'No captures yet',
              style: TextStyle(color: Colors.grey, fontSize: 16),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: _notes.length,
      itemBuilder: (ctx, index) {
        final note = _notes[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () => _openNoteDetail(note),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      _statusBadge(note.status, cs),
                      const SizedBox(width: 8),
                      if (note.category != null && note.category!.isNotEmpty)
                        _categoryBadge(note.category!),
                      if (note.urgency != null && note.urgency != 'normal') ...[
                        const SizedBox(width: 8),
                        _urgencyBadge(note.urgency!),
                      ],
                      const Spacer(),
                      if (note.hasAudio)
                        Icon(Icons.volume_up, size: 16, color: cs.primary),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    note.transcript != null && note.transcript!.trim().isNotEmpty
                        ? note.transcript!
                        : (note.status == 'transcribing'
                            ? 'Transcribing recording...'
                            : note.status == 'received'
                                ? 'Queued for transcription'
                                : '(No transcript available)'),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontStyle: note.transcript == null ? FontStyle.italic : FontStyle.normal,
                      color: note.transcript == null ? Colors.grey : cs.onSurface,
                      fontSize: 15,
                      height: 1.3,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        note.captureId,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              fontFamily: 'monospace',
                            ),
                      ),
                      if (note.receivedAt != null)
                        Text(
                          note.receivedAt!.replaceFirst('T', ' ').replaceFirst('Z', ' UTC'),
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _statusBadge(String status, ColorScheme cs) {
    Color bg;
    Color fg;
    switch (status) {
      case 'reviewed':
        bg = const Color(0xFF003829);
        fg = cs.primary;
        break;
      case 'transcribed':
        bg = const Color(0xFF1E2838);
        fg = const Color(0xFF8FD8FF);
        break;
      case 'transcribing':
        bg = const Color(0xFF382D10);
        fg = const Color(0xFFFFD56B);
        break;
      case 'received':
        bg = const Color(0xFF262626);
        fg = const Color(0xFFD4D4D4);
        break;
      default:
        bg = const Color(0xFF381010);
        fg = const Color(0xFFFF8B8B);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(6)),
      child: Text(
        status.toUpperCase(),
        style: TextStyle(color: fg, fontSize: 11, fontWeight: FontWeight.bold),
      ),
    );
  }

  Widget _categoryBadge(String category) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: const Color(0xFF342A5A),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        category,
        style: const TextStyle(color: Color(0xFFC4B6FF), fontSize: 11),
      ),
    );
  }

  Widget _urgencyBadge(String urgency) {
    final isHigh = urgency == 'high';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: isHigh ? const Color(0xFF4A1010) : const Color(0xFF1E2838),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        urgency,
        style: TextStyle(
          color: isHigh ? const Color(0xFFFF8B8B) : const Color(0xFF8FD8FF),
          fontSize: 11,
        ),
      ),
    );
  }
}

class _NoteDetailSheet extends StatefulWidget {
  final Note note;
  final ApiClient client;
  final VoidCallback onUpdated;

  const _NoteDetailSheet({
    required this.note,
    required this.client,
    required this.onUpdated,
  });

  @override
  State<_NoteDetailSheet> createState() => _NoteDetailSheetState();
}

class _NoteDetailSheetState extends State<_NoteDetailSheet> {
  late TextEditingController _transcriptController;
  late String _category;
  late String _urgency;
  late bool _actionable;

  AudioPlayer? _player;
  bool _isPlaying = false;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;
  bool _isSaving = false;

  final List<String> _categories = [
    'thought',
    'todo',
    'meeting',
    'idea',
    'reference',
    'unreviewed',
  ];

  final List<String> _urgencies = ['low', 'normal', 'high'];

  @override
  void initState() {
    super.initState();
    _transcriptController = TextEditingController(text: widget.note.transcript ?? '');
    _category = widget.note.category ?? 'unreviewed';
    _urgency = widget.note.urgency ?? 'normal';
    _actionable = widget.note.actionable ?? false;

    if (widget.note.hasAudio) {
      _initAudio();
    }
  }

  Future<void> _initAudio() async {
    _player = AudioPlayer();
    final url = widget.client.audioUrl(widget.note.captureId);
    try {
      await _player!.setUrl(url);
      _player!.playerStateStream.listen((state) {
        if (mounted) {
          setState(() {
            _isPlaying = state.playing;
          });
        }
      });
      _player!.positionStream.listen((pos) {
        if (mounted) setState(() => _position = pos);
      });
      _player!.durationStream.listen((dur) {
        if (mounted) setState(() => _duration = dur ?? Duration.zero);
      });
    } catch (_) {
      // Audio playback not available
    }
  }

  @override
  void dispose() {
    _transcriptController.dispose();
    _player?.dispose();
    super.dispose();
  }

  Future<void> _saveCorrection() async {
    setState(() => _isSaving = true);
    try {
      await widget.client.patchNote(widget.note.captureId, {
        'transcript': _transcriptController.text,
        'category': _category,
        'urgency': _urgency,
        'actionable': _actionable,
      });
      widget.onUpdated();
      if (mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Note updated successfully')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Capture ${widget.note.captureId}',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // Audio player bar
            if (widget.note.hasAudio && _player != null) ...[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: const Color(0xFF1C2A2B),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    IconButton(
                      icon: Icon(_isPlaying ? Icons.pause : Icons.play_arrow),
                      color: cs.primary,
                      onPressed: () {
                        if (_isPlaying) {
                          _player!.pause();
                        } else {
                          _player!.play();
                        }
                      },
                    ),
                    Expanded(
                      child: Slider(
                        value: _position.inMilliseconds
                            .toDouble()
                            .clamp(0.0, _duration.inMilliseconds.toDouble()),
                        max: _duration.inMilliseconds.toDouble() > 0
                            ? _duration.inMilliseconds.toDouble()
                            : 1.0,
                        onChanged: (val) {
                          _player!.seek(Duration(milliseconds: val.toInt()));
                        },
                      ),
                    ),
                    Text(
                      '${_position.inSeconds}s / ${_duration.inSeconds}s',
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],
            // Transcript edit
            TextFormField(
              controller: _transcriptController,
              maxLines: 6,
              decoration: const InputDecoration(
                labelText: 'Transcript / Correction',
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 16),
            // Category & Urgency row
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: _category,
                    decoration: const InputDecoration(labelText: 'Category'),
                    items: _categories
                        .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                        .toList(),
                    onChanged: (val) {
                      if (val != null) setState(() => _category = val);
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: _urgency,
                    decoration: const InputDecoration(labelText: 'Urgency'),
                    items: _urgencies
                        .map((u) => DropdownMenuItem(value: u, child: Text(u)))
                        .toList(),
                    onChanged: (val) {
                      if (val != null) setState(() => _urgency = val);
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Actionable Task / Todo'),
              value: _actionable,
              onChanged: (val) => setState(() => _actionable = val),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: _isSaving ? null : _saveCorrection,
              icon: _isSaving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black),
                    )
                  : const Icon(Icons.check),
              label: Text(_isSaving ? 'Saving...' : 'Save Correction'),
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
