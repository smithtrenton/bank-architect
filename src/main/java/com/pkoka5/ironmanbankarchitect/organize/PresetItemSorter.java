package com.pkoka5.ironmanbankarchitect.organize;

import com.pkoka5.ironmanbankarchitect.catalog.ClassificationNames;
import com.pkoka5.ironmanbankarchitect.catalog.ItemCategory;
import com.pkoka5.ironmanbankarchitect.organize.layout.ItemSetCatalog;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;

public final class PresetItemSorter
{
	private PresetItemSorter()
	{
	}

	public static List<BankPreviewItem> sort(BankCategory category, List<BankPreviewItem> items)
	{
		return sort(category, items, GearStatsSource.NONE);
	}

	public static List<BankPreviewItem> sort(BankCategory category, List<BankPreviewItem> items,
		GearStatsSource gearStats)
	{
		switch (category.getSortMode())
		{
			case MAIN:
				return IronmanMainItemSorter.sort(items);
			case GEAR:
				return GearItemSorter.layout(items, gearStats);
			case CURRENCY:
				return CurrencyItemSorter.sort(items);
			case SUPPLIES:
				return SupplyItemSorter.sort(items);
			case HERBLORE:
				return HerbloreItemSorter.layout(items);
			case FARMING:
				return FarmingItemSorter.layout(items, 0);
			case TELEPORTS:
				return TeleportItemSorter.sort(items);
			case CLUES:
				return sortClues(items);
			case TOOLS:
				return ToolItemSorter.sort(items);
			case RESOURCES:
				return ResourceItemSorter.sort(items);
			case BOSS_LOOT:
				return sortBossLoot(items);
			case REVIEW:
				return sortReview(items);
			case GENERIC:
			default:
				return sortGeneric(category, items);
		}
	}

	private static List<BankPreviewItem> sortGeneric(BankCategory category, List<BankPreviewItem> items)
	{
		List<BankPreviewItem> sorted = new ArrayList<>(items);
		sorted.sort(Comparator
			.comparingInt((BankPreviewItem item) -> subgroupRank(category.getKey(), item))
			.thenComparing(item -> normalizedName(item.getDisplayName()))
			.thenComparingInt(BankPreviewItem::getItemId));
		return sorted;
	}

	private static List<BankPreviewItem> sortClues(List<BankPreviewItem> items)
	{
		List<BankPreviewItem> sorted = new ArrayList<>(items);
		sorted.sort(Comparator
			.comparingInt(PresetItemSorter::clueRank)
			.thenComparingInt(item -> ItemSetCatalog.cosmeticFamilyRankOf(item.getItemId()))
			.thenComparing(PresetItemSorter::clueFamily)
			.thenComparing(item -> normalizedName(item.getDisplayName()))
			.thenComparingInt(BankPreviewItem::getItemId));
		return sorted;
	}

	/**
	 * Keeps a cosmetic family adjacent where plain alphabetical order would
	 * scatter it. Recoloured cosmetics lead with their colour word, so sorting
	 * them by name alone files each partyhat or dye next to whatever else
	 * shares its colour instead of next to the rest of its family. Families
	 * come from the set catalogue by exact ID, so a lookalike name such as the
	 * plain wig disguise never rides along with the real partyhats.
	 */
	private static String clueFamily(BankPreviewItem item)
	{
		return ItemSetCatalog.cosmeticFamilyOf(item.getItemId())
			.map(PresetItemSorter::normalizedName)
			.orElseGet(() -> normalizedName(item.getDisplayName()));
	}

	private static List<BankPreviewItem> sortBossLoot(List<BankPreviewItem> items)
	{
		List<BankPreviewItem> sorted = new ArrayList<>(items);
		sorted.sort(Comparator
			.comparingInt(PresetItemSorter::bossLootRank)
			.thenComparing(PresetItemSorter::bossLootFamily)
			.thenComparing(item -> normalizedName(item.getDisplayName()))
			.thenComparingInt(BankPreviewItem::getItemId));
		return sorted;
	}

	private static List<BankPreviewItem> sortReview(List<BankPreviewItem> items)
	{
		List<BankPreviewItem> sorted = new ArrayList<>(items);
		sorted.sort(Comparator
			.comparingInt(ReviewItemSorter::rank)
			.thenComparing(item -> normalizedName(item.getDisplayName()))
			.thenComparingInt(BankPreviewItem::getItemId));
		return sorted;
	}

	static int subgroupRank(String categoryKey, BankPreviewItem item)
	{
		String name = normalizedName(item.getDisplayName());
		String subcategory = normalizedName(item.getSubcategory());

		if ("currency-utilities".equals(categoryKey))
		{
			return rank(name, subcategory,
				group(76),
				group(77),
				group(78),
				group(79));
		}

		if ("teleports-runes".equals(categoryKey))
		{
			if (item.getItemCategory() == ItemCategory.RUNE || containsAny(name, ClassificationNames.group(148)))
			{
				return 0;
			}
			return rank(name, subcategory,
				group(80),
				group(81),
				group(82));
		}

		if ("combat-gear".equals(categoryKey))
		{
			return GearItemSorter.rank(item);
		}

		if ("potions-food".equals(categoryKey))
		{
			return rank(name, subcategory,
				group(83),
				group(84),
				group(85));
		}

		if ("farming-herblore".equals(categoryKey))
		{
			return herbloreSpilloverRank(item);
		}

		if ("resources".equals(categoryKey))
		{
			return rank(name, subcategory,
				group(86),
				group(87),
				group(88),
				group(89),
				group(90),
				group(91),
				group(92),
				group(93));
		}

		if ("storage-cleanup".equals(categoryKey))
		{
			return ReviewItemSorter.rank(item);
		}

		return 50;
	}

	static int herbloreSpilloverRank(BankPreviewItem item)
	{
		String name = normalizedName(item.getDisplayName());
		String subcategory = normalizedName(item.getSubcategory());
		return rank(name, subcategory,
			group(94),
			group(95),
			group(96),
			group(97),
			group(98));
	}

	public static String subgroupLabel(BankCategory category, BankPreviewItem item)
	{
		if (category.getSortMode() != BankCategorySortMode.REVIEW)
		{
			return "";
		}

		return ReviewItemSorter.label(item);
	}

	private static int rank(String name, String subcategory, Group... groups)
	{
		for (Group group : groups)
		{
			for (String needle : group.needles)
			{
				if (name.contains(needle))
				{
					return group.rank;
				}
			}
		}

		return 50;
	}

	private static Group group(int index)
	{
		String[] row = ClassificationNames.group(index);
		return new Group(Integer.parseInt(row[0]), Arrays.copyOfRange(row, 1, row.length));
	}

	private static boolean containsAny(String value, String... needles)
	{
		for (String needle : needles)
		{
			if (value.contains(needle))
			{
				return true;
			}
		}

		return false;
	}

	private static String normalizedName(String value)
	{
		return value == null ? "" : value.toLowerCase();
	}

	private static int clueRank(BankPreviewItem item)
	{
		String name = normalizedName(item.getDisplayName());
		String[] order = ClassificationNames.group(149);
		for (int i = 0; i < order.length; i++)
		{
			if (name.contains("(" + order[i] + ")"))
			{
				return i;
			}
		}
		return 20;
	}


	private static int bossLootRank(BankPreviewItem item)
	{
		if (item.getItemCategory() == ItemCategory.UNIQUE)
		{
			String subcategory = normalizedName(item.getSubcategory());
			if (subcategory.contains("weapon-upgrade")) return 0;
			if (subcategory.contains("equipment-upgrade")) return 10;
			if (subcategory.contains("charge")) return 20;
			return 30;
		}
		if (item.getItemCategory() == ItemCategory.GEAR)
		{
			return 100;
		}
		return 50;
	}

	private static String bossLootFamily(BankPreviewItem item)
	{
		String name = normalizedName(item.getDisplayName());
		if (name.contains("crystal weapon seed")) return "crystal-weapon-seed";
		if (name.endsWith(" page")) return "charge-page";
		return name;
	}

	private static final class Group
	{
		private final int rank;
		private final String[] needles;

		private Group(int rank, String[] needles)
		{
			this.rank = rank;
			this.needles = needles;
		}
	}
}
