"""Candidate genres for exporting Japanese retail goods (sourced after sale).

Each genre is only a starting search phrase: export_research.py measures
what Japan-located sellers actually sell in it and whether the exact same
product (matched by JAN code) can be bought new in Japan for less than it
nets on eBay. Nothing here is a judgement that a genre is profitable.

`size` picks the international shipping estimate (see
Config.export_shipping_jpy). `caution` is surfaced next to the genre in
every report, for the risks the numbers alone won't show.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportGenre:
    key: str
    label: str
    query: str
    size: str  # "small" (<=0.5kg), "medium" (<=1.5kg), "large" (<=3kg)
    caution: str = ""


GENRES: list[ExportGenre] = [
    ExportGenre("gunpla", "ガンプラ・バンダイ模型", "bandai gunpla model kit", "medium"),
    ExportGenre("anime_figure", "アニメフィギュア", "anime figure japan", "medium",
                "版権物: VeRO（権利者による削除）とコピー品の混入に注意"),
    ExportGenre("pokemon_tcg", "ポケカ日本語版（未開封）", "pokemon card japanese booster box sealed", "small",
                "相場の変動が激しく、偽物対策で高額取引は要注意"),
    ExportGenre("onepiece_tcg", "ワンピースカード日本語版", "one piece card game japanese booster box", "small",
                "相場の変動が激しい"),
    ExportGenre("fountain_pen", "国産万年筆", "pilot fountain pen japan", "small"),
    ExportGenre("stationery", "日本限定文具", "japan limited pen zebra pentel uni", "small"),
    ExportGenre("kitchen_knife", "和包丁", "japanese kitchen knife", "medium",
                "刃物: 配送方法・仕向国によって発送できない場合がある（豪州は特に厳しい）"),
    ExportGenre("hand_tools", "日本製工具", "japanese tools pliers engineer hozan", "medium"),
    ExportGenre("fishing_lure", "国産ルアー", "megabass jackall lure japan", "small"),
    ExportGenre("tamagotchi", "たまごっち・日本版玩具", "tamagotchi japan version", "small"),
    ExportGenre("tomica", "トミカ", "tomica takara tomy japan", "small"),
    ExportGenre("beyblade", "ベイブレードX", "beyblade x takara tomy", "small"),
    ExportGenre("mini4wd", "タミヤ ミニ四駆", "tamiya mini 4wd japan", "small"),
    ExportGenre("seiko_jdm", "セイコー国内モデル", "seiko japan made jdm watch", "small",
                "高単価: 新規アカウントの販売上限（金額）を圧迫しやすい"),
    ExportGenre("switch_jp", "日本版ゲームソフト", "nintendo switch japanese version game", "small"),
    ExportGenre("sanrio", "サンリオ日本限定", "sanrio japan limited", "small",
                "版権物: VeRO（権利者による削除）に注意"),
    ExportGenre("skincare", "日本のスキンケア", "japanese sunscreen skincare", "small",
                "液体・エアゾール: 配送制限あり。米国では化粧品規制の対象"),
    ExportGenre("camera_acc", "カメラ用品（新品）", "japan camera lens new", "medium",
                "中古は古物商許可の取得後に対象を広げる"),
]
