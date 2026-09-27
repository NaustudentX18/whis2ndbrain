import 'package:flutter/material.dart';

/// Whis2ndBrain design tokens — from DESIGN.md
/// Canvas:  #101A1D
/// Surface: #172427 (cards), #1C2A2B (elevated)
/// Text:    #F1F4E9
/// Mint:    #BDF4D7 (primary), #8FDFBD (secondary)
/// Lilac:   #C4B6FF (accent)

const _canvas = Color(0xFF101A1D);
const _surface = Color(0xFF172427);
const _surfaceElevated = Color(0xFF1C2A2B);
const _onSurface = Color(0xFFF1F4E9);
const _mintPrimary = Color(0xFFBDF4D7);
const _mintSecondary = Color(0xFF8FDFBD);
const _lilac = Color(0xFFC4B6FF);
const _onPrimary = Color(0xFF00201A);

ColorScheme get whisColorScheme => const ColorScheme(
      brightness: Brightness.dark,
      primary: _mintPrimary,
      onPrimary: _onPrimary,
      primaryContainer: Color(0xFF003829),
      onPrimaryContainer: _mintSecondary,
      secondary: _lilac,
      onSecondary: Color(0xFF1E1242),
      secondaryContainer: Color(0xFF342A5A),
      onSecondaryContainer: _lilac,
      tertiary: _mintSecondary,
      onTertiary: _onPrimary,
      tertiaryContainer: Color(0xFF002F22),
      onTertiaryContainer: _mintPrimary,
      error: Color(0xFFFFB4AB),
      onError: Color(0xFF690005),
      errorContainer: Color(0xFF93000A),
      onErrorContainer: Color(0xFFFFDAD6),
      surface: _surface,
      onSurface: _onSurface,
      surfaceContainerHighest: _surfaceElevated,
      outline: Color(0xFF4D6960),
      shadow: Color(0xFF000000),
      inverseSurface: _onSurface,
      onInverseSurface: _canvas,
      inversePrimary: Color(0xFF006B51),
    );

ThemeData get whisTheme => ThemeData(
      useMaterial3: true,
      colorScheme: whisColorScheme,
      scaffoldBackgroundColor: _canvas,
      cardTheme: const CardThemeData(
        color: _surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: _canvas,
        foregroundColor: _onSurface,
        elevation: 0,
        centerTitle: false,
      ),
      navigationBarTheme: const NavigationBarThemeData(
        backgroundColor: _surfaceElevated,
        indicatorColor: Color(0xFF003829),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: _surface,
        selectedColor: const Color(0xFF003829),
        labelStyle: const TextStyle(color: _onSurface),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      textTheme: const TextTheme(
        headlineLarge: TextStyle(color: _onSurface, fontWeight: FontWeight.w600),
        headlineMedium: TextStyle(color: _onSurface, fontWeight: FontWeight.w600),
        titleLarge: TextStyle(color: _onSurface, fontWeight: FontWeight.w500),
        titleMedium: TextStyle(color: _onSurface),
        bodyLarge: TextStyle(color: _onSurface),
        bodyMedium: TextStyle(color: _onSurface),
        bodySmall: TextStyle(color: Color(0xFFB2C9C4)),
        labelLarge: TextStyle(color: _mintPrimary, fontWeight: FontWeight.w600),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: _surfaceElevated,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: _mintPrimary, width: 2),
        ),
        labelStyle: const TextStyle(color: Color(0xFFB2C9C4)),
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: _mintPrimary,
        foregroundColor: _onPrimary,
      ),
      dividerTheme: const DividerThemeData(
        color: Color(0xFF2A3C3A),
        thickness: 1,
      ),
    );
