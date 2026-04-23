import '../../../core/constants.dart';

class User {
  final String id;
  final String email;
  final String? name;
  final bool isAdmin;
  final String? avatarUrl;

  const User({
    required this.id,
    required this.email,
    this.name,
    this.isAdmin = false,
    this.avatarUrl,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    final rawAvatar = json['avatar_url'] as String?;
    String? fullAvatarUrl;
    if (rawAvatar != null && rawAvatar.isNotEmpty) {
      fullAvatarUrl = rawAvatar.startsWith('http')
          ? rawAvatar
          : '${AppConstants.apiBaseUrl}$rawAvatar';
    }

    return User(
      id: json['id']?.toString() ?? '',
      email: json['email'] as String? ?? '',
      name: json['name'] as String?,
      isAdmin: json['is_admin'] as bool? ?? false,
      avatarUrl: fullAvatarUrl,
    );
  }
}
