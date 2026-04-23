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

  // Reader mode (per book)
  static String getInteractionMode(String bookId) {
    return _settingsBox.get('interactionMode_$bookId',
        defaultValue: 'play') as String;
  }

  static Future<void> setInteractionMode(String bookId, String mode) {
    return _settingsBox.put('interactionMode_$bookId', mode);
  }

  static bool getToolbarVisible(String bookId) {
    return _settingsBox.get('toolbarVisible_$bookId',
        defaultValue: true) as bool;
  }

  static Future<void> setToolbarVisible(String bookId, bool visible) {
    return _settingsBox.put('toolbarVisible_$bookId', visible);
  }
}
