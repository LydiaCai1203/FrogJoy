class User {
  final String id;
  final String email;
  final bool isAdmin;
  final String? avatarUrl;

  const User({
    required this.id,
    required this.email,
    this.isAdmin = false,
    this.avatarUrl,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id']?.toString() ?? '',
      email: json['email'] as String? ?? '',
      isAdmin: json['is_admin'] as bool? ?? false,
      avatarUrl: json['avatar_url'] as String?,
    );
  }
}
