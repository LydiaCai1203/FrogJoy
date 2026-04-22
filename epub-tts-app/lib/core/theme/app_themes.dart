import 'package:flutter/material.dart';

enum AppTheme {
  freshGreen,
  night,
  eyeCare;

  String get label {
    switch (this) {
      case AppTheme.freshGreen:
        return '日间';
      case AppTheme.night:
        return '夜间';
      case AppTheme.eyeCare:
        return '护眼';
    }
  }

  Color get previewColor {
    switch (this) {
      case AppTheme.freshGreen:
        return const Color(0xFFF5F5F5);
      case AppTheme.night:
        return const Color(0xFF3D3A32);
      case AppTheme.eyeCare:
        return const Color(0xFFF8F2DC);
    }
  }

  static AppTheme fromString(String value) {
    switch (value) {
      case 'night':
        return AppTheme.night;
      case 'eye-care':
      case 'eyeCare':
        return AppTheme.eyeCare;
      case 'fresh-green':
      case 'freshGreen':
      case 'day':
      default:
        return AppTheme.freshGreen;
    }
  }

  String toApiString() {
    switch (this) {
      case AppTheme.freshGreen:
        return 'fresh-green';
      case AppTheme.night:
        return 'night';
      case AppTheme.eyeCare:
        return 'eye-care';
    }
  }
}

class AppThemes {
  AppThemes._();

  static ThemeData getTheme(AppTheme theme) {
    switch (theme) {
      case AppTheme.freshGreen:
        return _freshGreenTheme;
      case AppTheme.night:
        return _nightTheme;
      case AppTheme.eyeCare:
        return _eyeCareTheme;
    }
  }

  // 日间 — 浅灰白底，绿色点缀
  static final _freshGreenTheme = ThemeData(
    brightness: Brightness.light,
    scaffoldBackgroundColor: const Color(0xFFF6F7F5),
    colorScheme: const ColorScheme.light(
      primary: Color(0xFF4CAF50),
      onPrimary: Colors.white,
      surface: Color(0xFFFFFFFF),
      onSurface: Color(0xFF1E1E1E),
      secondary: Color(0xFFEFF3EC),
      error: Color(0xFFDC2626),
    ),
    cardColor: const Color(0xFFFFFFFF),
    appBarTheme: const AppBarTheme(
      backgroundColor: Color(0xFFF6F7F5),
      foregroundColor: Color(0xFF1E1E1E),
      elevation: 0,
    ),
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: Color(0xFF4CAF50),
      foregroundColor: Colors.white,
    ),
  );

  static const _nightYellow = Color(0xFFE8C84A);
  static const _nightGreen = Color(0xFF66BB6A);

  // 夜间 — 深灰底，绿+暖黄双色
  static final _nightTheme = ThemeData(
    brightness: Brightness.dark,
    scaffoldBackgroundColor: const Color(0xFF2C2C2C),
    colorScheme: ColorScheme.dark(
      primary: _nightGreen,
      onPrimary: Colors.white,
      surface: const Color(0xFF383838),
      onSurface: const Color(0xFFE8E4DC),
      tertiary: _nightYellow,
      onTertiary: const Color(0xFF2C2C2C),
      secondary: const Color(0xFF3D3A32),
      error: const Color(0xFFFF6B6B),
    ),
    cardColor: const Color(0xFF383838),
    appBarTheme: const AppBarTheme(
      backgroundColor: Color(0xFF2C2C2C),
      foregroundColor: Color(0xFFE8E4DC),
      elevation: 0,
    ),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: _nightYellow,
      foregroundColor: const Color(0xFF2C2C2C),
    ),
    navigationBarTheme: NavigationBarThemeData(
      indicatorColor: _nightGreen.withValues(alpha: 0.15),
      iconTheme: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) {
          return IconThemeData(color: _nightYellow);
        }
        return const IconThemeData(color: Color(0xFF888880));
      }),
      labelTextStyle: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) {
          return TextStyle(color: _nightYellow, fontSize: 12);
        }
        return const TextStyle(color: Color(0xFF888880), fontSize: 12);
      }),
    ),
    iconButtonTheme: IconButtonThemeData(
      style: ButtonStyle(
        foregroundColor: WidgetStatePropertyAll(_nightYellow),
      ),
    ),
    listTileTheme: ListTileThemeData(
      iconColor: _nightYellow.withValues(alpha: 0.8),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: _nightYellow,
    ),
    dividerColor: const Color(0xFF4A4740),
  );

  // 护眼 — 暖黄底，橄榄绿点缀
  static final _eyeCareTheme = ThemeData(
    brightness: Brightness.light,
    scaffoldBackgroundColor: const Color(0xFFF8F2DC),
    colorScheme: const ColorScheme.light(
      primary: Color(0xFF6B9E3C),
      onPrimary: Colors.white,
      surface: Color(0xFFF3ECCE),
      onSurface: Color(0xFF4A4030),
      secondary: Color(0xFFF0E8C8),
      error: Color(0xFFDC2626),
    ),
    cardColor: const Color(0xFFF3ECCE),
    appBarTheme: const AppBarTheme(
      backgroundColor: Color(0xFFF8F2DC),
      foregroundColor: Color(0xFF4A4030),
      elevation: 0,
    ),
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: Color(0xFF6B9E3C),
      foregroundColor: Colors.white,
    ),
  );
}
