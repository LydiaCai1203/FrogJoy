import 'package:hive_flutter/hive_flutter.dart';
import '../constants.dart';

class LocalStorage {
  LocalStorage._();

  static late Box _settingsBox;

  static Future<void> init() async {
    await Hive.initFlutter();
    _settingsBox = await Hive.openBox(AppConstants.settingsBox);
  }

  // Theme
  static String getTheme([String? userId]) {
    final key = userId != null ? 'theme_$userId' : 'theme';
    return _settingsBox.get(key, defaultValue: 'day') as String;
  }

  static Future<void> setTheme(String theme, [String? userId]) {
    final key = userId != null ? 'theme_$userId' : 'theme';
    return _settingsBox.put(key, theme);
  }

  // Font size
  static double getFontSize() {
    return _settingsBox.get('fontSize',
        defaultValue: AppConstants.defaultFontSize) as double;
  }

  static Future<void> setFontSize(double size) {
    return _settingsBox.put('fontSize', size);
  }
}
