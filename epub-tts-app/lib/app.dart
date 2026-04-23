import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'core/theme/app_themes.dart';
import 'core/theme/theme_provider.dart';
import 'features/auth/domain/auth_provider.dart';
import 'features/auth/presentation/auth_page.dart';
import 'features/bookshelf/presentation/bookshelf_page.dart';
import 'features/profile/presentation/profile_page.dart';
import 'features/reader/presentation/reader_page.dart';
import 'features/splash/splash_page.dart';

GoRouter buildRouter(WidgetRef ref) {
  return GoRouter(
    redirect: (context, state) {
      final authState = ref.read(authProvider);
      final isLoggedIn = authState.valueOrNull?.isAuthenticated ?? false;
      final onLoginPage = state.uri.path == '/login';
      if (!isLoggedIn && !onLoginPage) return '/login';
      if (isLoggedIn && onLoginPage) return '/';
      return null;
    },
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return MainShell(navigationShell: navigationShell);
        },
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/',
                builder: (context, state) => const BookshelfPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/profile',
                builder: (context, state) => const ProfilePage(),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: '/login',
        builder: (context, state) => const AuthPage(),
      ),
      GoRoute(
        path: '/book/:bookId',
        builder: (context, state) {
          final bookId = state.pathParameters['bookId']!;
          return ReaderPage(bookId: bookId);
        },
      ),
    ],
  );
}

class BookReaderApp extends ConsumerStatefulWidget {
  const BookReaderApp({super.key});

  @override
  ConsumerState<BookReaderApp> createState() => _BookReaderAppState();
}

class _BookReaderAppState extends ConsumerState<BookReaderApp> {
  late final GoRouter _router;
  bool _splashDone = false;

  @override
  void initState() {
    super.initState();
    _router = buildRouter(ref);

    // Listen to auth changes and refresh router
    ref.listenManual(authProvider, (_, __) {
      _router.refresh();
    });
  }

  @override
  void dispose() {
    _router.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final currentTheme = ref.watch(themeProvider);

    if (!_splashDone) {
      return MaterialApp(
        debugShowCheckedModeBanner: false,
        home: SplashPage(
          onFinished: () => setState(() => _splashDone = true),
        ),
      );
    }

    return MaterialApp.router(
      title: 'FrogJoy',
      debugShowCheckedModeBanner: false,
      theme: AppThemes.getTheme(currentTheme),
      routerConfig: _router,
    );
  }
}

class MainShell extends ConsumerWidget {
  final StatefulNavigationShell navigationShell;

  const MainShell({super.key, required this.navigationShell});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final user = ref.watch(currentUserProvider);
    final avatarUrl = user?.avatarUrl;
    final isProfileSelected = navigationShell.currentIndex == 1;

    final isBookshelf = navigationShell.currentIndex == 0;

    return Scaffold(
      extendBody: true,
      extendBodyBehindAppBar: true,
      body: navigationShell,
      bottomNavigationBar: Theme(
        data: theme.copyWith(
          navigationBarTheme: NavigationBarThemeData(
            labelTextStyle: WidgetStateProperty.resolveWith((states) {
              final selected = states.contains(WidgetState.selected);
              return TextStyle(
                fontSize: 11,
                fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                color: isBookshelf
                    ? (selected ? Colors.white : Colors.white70)
                    : (selected
                        ? theme.colorScheme.primary
                        : theme.colorScheme.onSurface.withValues(alpha: 0.6)),
              );
            }),
            iconTheme: WidgetStateProperty.resolveWith((states) {
              final selected = states.contains(WidgetState.selected);
              return IconThemeData(
                color: isBookshelf
                    ? (selected ? Colors.white : Colors.white70)
                    : (selected
                        ? theme.colorScheme.primary
                        : theme.colorScheme.onSurface.withValues(alpha: 0.6)),
              );
            }),
          ),
        ),
        child: NavigationBar(
          selectedIndex: navigationShell.currentIndex,
          onDestinationSelected: (index) {
            navigationShell.goBranch(index,
                initialLocation: index == navigationShell.currentIndex);
          },
          height: 56,
          labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
          backgroundColor: Colors.transparent,
          surfaceTintColor: Colors.transparent,
          indicatorColor: Colors.transparent,
          destinations: [
            const NavigationDestination(
              icon: Icon(Icons.menu_book_outlined),
              selectedIcon: Icon(Icons.menu_book),
              label: '书架',
            ),
            NavigationDestination(
              icon: _AvatarIcon(
                url: avatarUrl,
                selected: isProfileSelected,
                theme: theme,
              ),
              selectedIcon: _AvatarIcon(
                url: avatarUrl,
                selected: true,
                theme: theme,
              ),
              label: '我的',
            ),
          ],
        ),
      ),
    );
  }
}

class _AvatarIcon extends StatelessWidget {
  final String? url;
  final bool selected;
  final ThemeData theme;

  const _AvatarIcon({
    required this.url,
    required this.selected,
    required this.theme,
  });

  @override
  Widget build(BuildContext context) {
    const size = 24.0;
    final borderColor = selected
        ? theme.colorScheme.primary
        : theme.colorScheme.onSurface.withValues(alpha: 0.3);

    if (url != null && url!.isNotEmpty) {
      return Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: borderColor, width: selected ? 1.5 : 1),
        ),
        child: ClipOval(
          child: CachedNetworkImage(
            imageUrl: url!,
            width: size,
            height: size,
            fit: BoxFit.cover,
            errorWidget: (_, __, ___) => _fallback(),
          ),
        ),
      );
    }

    return _fallback();
  }

  Widget _fallback() {
    return Image.asset(
      'assets/images/logo.png',
      width: 24,
      height: 24,
    );
  }
}
