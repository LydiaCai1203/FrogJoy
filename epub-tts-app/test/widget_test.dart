import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:book_reader_app/app.dart';

void main() {
  testWidgets('App renders', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: BookReaderApp()),
    );
    expect(find.text('FrogJoy'), findsOneWidget);
  });
}
