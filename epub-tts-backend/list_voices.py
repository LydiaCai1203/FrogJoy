#!/usr/bin/env python3
"""
列出所有可用的微软语音
"""
import asyncio
import edge_tts

async def list_voices():
    voices = await edge_tts.list_voices()
    
    # 按语言分组
    by_lang = {}
    for v in voices:
        locale = v["Locale"]
        lang = locale.split("-")[0]
        if lang not in by_lang:
            by_lang[lang] = []
        by_lang[lang].append(v)
    
    # 常用语言优先显示
    priority_langs = ["zh", "en", "ja", "ko", "fr", "de", "es"]
    
    print(f"总共 {len(voices)} 种语音\n")
    print("=" * 60)
    
    # 先显示常用语言
    for lang in priority_langs:
        if lang in by_lang:
            print_lang_voices(lang, by_lang[lang])
            del by_lang[lang]
    
    # 显示其他语言
    for lang in sorted(by_lang.keys()):
        print_lang_voices(lang, by_lang[lang])

def print_lang_voices(lang, voices):
    lang_names = {
        "zh": "中文",
        "en": "英文", 
        "ja": "日文",
        "ko": "韩文",
        "fr": "法文",
        "de": "德文",
        "es": "西班牙文",
    }
    
    name = lang_names.get(lang, lang.upper())
    print(f"\n【{name}】({len(voices)} 种)")
    print("-" * 40)
    
    for v in voices:
        short_name = v["ShortName"]
        gender = "♀" if v["Gender"] == "Female" else "♂"
        locale = v["Locale"]
        print(f"  {gender} {short_name:<35} ({locale})")

if __name__ == "__main__":
    asyncio.run(list_voices())

