import 'package:flutter/material.dart';
import '../api/api_client.dart';

class DeviceScreen extends StatefulWidget {
  final ApiClient client;

  const DeviceScreen({super.key, required this.client});

  @override
  State<DeviceScreen> createState() => _DeviceScreenState();
}

class _DeviceScreenState extends State<DeviceScreen> {
  Map<String, dynamic>? _telemetry;
  bool _isLoading = false;
  String? _errorMessage;
  bool _isPinging = false;

  @override
  void initState() {
    super.initState();
    _fetchTelemetry();
  }

  Future<void> _fetchTelemetry() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final res = await widget.client.getTelemetry();
      setState(() {
        _telemetry = res;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to load telemetry: $e';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _sendTestHeartbeat() async {
    setState(() => _isPinging = true);
    try {
      final res = await widget.client.sendHeartbeat({
        'device_id': 'pi-zero-2w',
        'queue_depth': 0,
        'battery_pct': 92.0,
        'wifi_rssi_dbm': -54,
        'firmware_version': '0.1.0-alpha',
        'spool_errors': 0,
      });
      setState(() {
        _telemetry = res;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Test heartbeat broadcasted via SSE')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Heartbeat failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isPinging = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Device & Hardware'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isLoading ? null : _fetchTelemetry,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _fetchTelemetry,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_errorMessage != null) ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF93000A),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _errorMessage!,
                  style: const TextStyle(color: Colors.white),
                ),
              ),
              const SizedBox(height: 16),
            ],
            _buildStatusHeader(cs),
            const SizedBox(height: 16),
            _buildTelemetryCard(cs),
            const SizedBox(height: 16),
            _buildGestureCard(cs),
            const SizedBox(height: 16),
            _buildHardwareActions(cs),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusHeader(ColorScheme cs) {
    final quality = _telemetry?['connection_quality'] as String? ?? 'unknown';
    Color badgeBg;
    Color badgeFg;
    IconData icon;

    switch (quality) {
      case 'online':
        badgeBg = const Color(0xFF003829);
        badgeFg = cs.primary;
        icon = Icons.check_circle_outline;
        break;
      case 'recent':
        badgeBg = const Color(0xFF1E2838);
        badgeFg = const Color(0xFF8FD8FF);
        icon = Icons.access_time;
        break;
      case 'stale':
        badgeBg = const Color(0xFF382D10);
        badgeFg = const Color(0xFFFFD56B);
        icon = Icons.warning_amber_outlined;
        break;
      default:
        badgeBg = const Color(0xFF381010);
        badgeFg = const Color(0xFFFF8B8B);
        icon = Icons.cloud_off;
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: badgeBg,
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: badgeFg, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Device Status: ${quality.toUpperCase()}',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: badgeFg,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _telemetry?['device_id'] != null
                        ? 'Paired: ${_telemetry!['device_id']}'
                        : 'No active device heartbeat registered yet',
                    style: TextStyle(color: cs.onSurface.withValues(alpha: 0.8)),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTelemetryCard(ColorScheme cs) {
    final battery = _telemetry?['battery_pct'];
    final wifi = _telemetry?['wifi_rssi_dbm'];
    final queue = _telemetry?['queue_depth'];
    final lastSeen = _telemetry?['last_seen_at'];
    final age = _telemetry?['age_seconds'];
    final errors = _telemetry?['spool_errors'];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Hardware Telemetry',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const Divider(height: 24),
            _metricRow(
              icon: Icons.battery_charging_full,
              label: 'Battery Level',
              value: battery != null ? '$battery%' : 'N/A',
              color: battery != null && battery < 20 ? cs.error : cs.primary,
            ),
            const SizedBox(height: 12),
            _metricRow(
              icon: Icons.wifi,
              label: 'WiFi Signal',
              value: wifi != null ? '$wifi dBm' : 'N/A',
            ),
            const SizedBox(height: 12),
            _metricRow(
              icon: Icons.queue_music,
              label: 'Queue Depth (on Pi)',
              value: queue != null ? '$queue capture(s)' : '0',
            ),
            const SizedBox(height: 12),
            _metricRow(
              icon: Icons.history,
              label: 'Last Seen',
              value: lastSeen != null
                  ? (age != null ? '${age.toInt()}s ago' : lastSeen.toString())
                  : 'Never',
            ),
            const SizedBox(height: 12),
            _metricRow(
              icon: Icons.bug_report_outlined,
              label: 'Spool Sync Errors',
              value: errors != null ? '$errors' : '0',
              color: errors != null && errors > 0 ? cs.error : null,
            ),
          ],
        ),
      ),
    );
  }

  Widget _metricRow({
    required IconData icon,
    required String label,
    required String value,
    Color? color,
  }) {
    return Row(
      children: [
        Icon(icon, size: 20, color: color ?? Colors.grey),
        const SizedBox(width: 12),
        Expanded(
          child: Text(label, style: const TextStyle(fontSize: 14)),
        ),
        Text(
          value,
          style: TextStyle(
            fontWeight: FontWeight.bold,
            fontSize: 14,
            color: color,
          ),
        ),
      ],
    );
  }

  Widget _buildGestureCard(ColorScheme cs) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.touch_app, color: cs.primary),
                const SizedBox(width: 8),
                Text(
                  'Recording Gesture',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF1C2A2B),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'State Machine: Click-to-Start / Click-to-Stop',
                    style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFFBDF4D7)),
                  ),
                  SizedBox(height: 6),
                  Text(
                    '1. Click button -> LED turns ON -> Recording starts.\n'
                    '2. Click button again -> LED blinks -> Audio finalised.\n'
                    '3. Auto-saved to durable spool on Pi -> Synced to host.\n'
                    '4. No long-press required; accidental taps filtered by 300ms debounce.',
                    style: TextStyle(fontSize: 13, height: 1.4),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHardwareActions(ColorScheme cs) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Actions & Testing',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _isPinging ? null : _sendTestHeartbeat,
              icon: _isPinging
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.sensors),
              label: Text(_isPinging ? 'Pinging...' : 'Simulate Pi Heartbeat (SSE Broadcast)'),
            ),
          ],
        ),
      ),
    );
  }
}
