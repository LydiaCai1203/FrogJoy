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

    return MaterialApp.router(
      title: 'FrogJoy',
      debugShowCheckedModeBanner: false,
      theme: AppThemes.getTheme(currentTheme),
      routerConfig: _router,
    );
  }
}

class MainShell extends StatelessWidget {
  final StatefulNavigationShell navigationShell;

  const MainShell({super.key, required this.navigationShell});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: (index) {
          navigationShell.goBranch(index,
              initialLocation: index == navigationShell.currentIndex);
        },
        height: 60,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        backgroundColor: theme.scaffoldBackgroundColor,
        indicatorColor: theme.colorScheme.primary.withValues(alpha: 0.12),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.menu_book_outlined),
            selectedIcon: Icon(Icons.menu_book),
            label: '书架',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: '我的',
          ),
        ],
      ),
    );
  }
}
