/// ChatScreen — 实时聊天界面.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../providers/chat_provider.dart';
import '../../providers/session_provider.dart';
import '../../providers/pulse_provider.dart';
import 'pulse_panel.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    // WebSocket 消息到达时自动滚动到底部
    final chat = context.read<ChatProvider>();
    chat.addListener(_onMessagesChanged);
  }

  void _onMessagesChanged() {
    final chat = context.read<ChatProvider>();
    if (chat.messages.isNotEmpty &&
        chat.messages.last.role == 'coach') {
      _scrollToBottom();
    }
  }

  @override
  void dispose() {
    context.read<ChatProvider>().removeListener(_onMessagesChanged);
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();

    final sessionId = context.read<SessionProvider>().sessionId;
    if (sessionId == null) return;

    setState(() => _sending = true);
    await context.read<ChatProvider>().sendMessage(
          sessionId: sessionId,
          message: text,
        );
    setState(() => _sending = false);
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final chat = context.watch<ChatProvider>();
    final pulse = context.watch<PulseProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('对话'),
        centerTitle: true,
      ),
      body: Column(
        children: [
          Expanded(
            child: chat.messages.isEmpty
                ? const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.chat_bubble_outline,
                            size: 64, color: CoachColors.lavenderGray),
                        SizedBox(height: 16),
                        Text('开始对话吧',
                            style: TextStyle(
                                fontSize: 16, color: CoachColors.deepMocha)),
                      ],
                    ),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16),
                    itemCount: chat.messages.length,
                    itemBuilder: (_, i) {
                      final msg = chat.messages[i];
                      return _ChatBubble(message: msg);
                    },
                  ),
          ),
          if (chat.pendingPulse != null)
            PulsePanel(
              pulse: chat.pendingPulse!,
              blockingMode: pulse.blockingMode,
              onAccept: () {
                final sid = context.read<SessionProvider>().sessionId;
                if (sid != null && chat.pendingPulse != null) {
                  chat.respondPulse(
                    sessionId: sid,
                    pulseId: chat.pendingPulse!.pulseId,
                    decision: 'accept',
                  );
                  pulse.recordPulse('accept');
                }
              },
              onRewrite: (content) {
                final sid = context.read<SessionProvider>().sessionId;
                if (sid != null && chat.pendingPulse != null) {
                  chat.respondPulse(
                    sessionId: sid,
                    pulseId: chat.pendingPulse!.pulseId,
                    decision: 'rewrite',
                  );
                  pulse.recordPulse('rewrite');
                  chat.sendMessage(
                    sessionId: sid,
                    message: content,
                  );
                }
              },
            ),
          _buildInputBar(),
        ],
      ),
    );
  }

  Widget _buildInputBar() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: const BoxDecoration(
        color: CoachColors.warmWhite,
        border: Border(top: BorderSide(color: CoachColors.lavenderGray)),
      ),
      child: SafeArea(
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _controller,
                decoration: const InputDecoration(
                  hintText: '输入消息...',
                  border: InputBorder.none,
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                ),
                maxLines: 3,
                minLines: 1,
                onSubmitted: (_) => _send(),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              onPressed: _sending ? null : _send,
              icon: _sending
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.send_rounded),
              color: CoachColors.deepMocha,
            ),
          ],
        ),
      ),
    );
  }
}

/// 消息气泡
class _ChatBubble extends StatelessWidget {
  final ChatMessage message;

  const _ChatBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.72,
        ),
        decoration: BoxDecoration(
          color: isUser ? CoachColors.lavenderGray : CoachColors.softBlue,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(isUser ? 16 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 16),
          ),
        ),
        child: Text(
          message.content,
          style: const TextStyle(fontSize: 15, color: CoachColors.deepMocha),
        ),
      ),
    );
  }
}
