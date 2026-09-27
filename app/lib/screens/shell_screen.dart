import 'package:flutter/material.dart';
import '../api/api_client.dart';
import 'device_screen.dart';
import 'notes_screen.dart';
import 'settings_screen.dart';

class ShellScreen extends StatefulWidget {
  final ApiClient client;

  const ShellScreen({super.key, required this.client});

  @override
  State<ShellScreen> createState() => _ShellScreenState();
}

class _ShellScreenState extends State<ShellScreen> {
  int _currentIndex = 0;

  late final List<Widget> _screens;

  @override
  void initState() {
    super.initState();
    _screens = [
      NotesScreen(client: widget.client),
      DeviceScreen(client: widget.client),
      SettingsScreen(client: widget.client),
    ];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.description_outlined),
            selectedIcon: Icon(Icons.description),
            label: 'Notes',
          ),
          NavigationDestination(
            icon: Icon(Icons.memory_outlined),
            selectedIcon: Icon(Icons.memory),
            label: 'Device',
          ),
          NavigationDestination(
            icon: Icon(Icons.tune_outlined),
            selectedIcon: Icon(Icons.tune),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}
