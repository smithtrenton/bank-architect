package com.pkoka5.ironmanbankarchitect.organize;

import com.pkoka5.ironmanbankarchitect.bank.BankItemSnapshot;
import com.pkoka5.ironmanbankarchitect.bank.BankSnapshot;
import com.pkoka5.ironmanbankarchitect.catalog.OrderedItemFamilies;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** Selects one owned tool per quick-access family, preserving bank placeholders. */
public final class IronmanQuickToolSelector
{
	private static final OrderedItemFamilies TABLE = new OrderedItemFamilies(
		IronmanQuickToolSelector.class.getResourceAsStream(
			"/com/pkoka5/ironmanbankarchitect/catalog/quick-tool-layout-families.tsv"), 0);

	private IronmanQuickToolSelector()
	{
	}

	static Set<Integer> select(BankSnapshot snapshot)
	{
		Set<Integer> owned = new LinkedHashSet<>();
		for (BankItemSnapshot item : snapshot.getItems())
		{
			// A bank placeholder preserves the player's tool choice while the
			// item is out of the bank. No inventory/equipment read is needed.
			owned.add(item.getItemId());
		}
		Set<Integer> selected = new LinkedHashSet<>();
		selectHighest(owned, tiers("HAMMER"), selected);
		selectHighest(owned, tiers("CHISEL"), selected);
		selectHighest(owned, tiers("PICKAXE"), selected);
		selectHighest(owned, tiers("AXE"), selected);
		return Collections.unmodifiableSet(selected);
	}

	static boolean isTieredTool(int itemId)
	{
		int rank = quickAccessRank(itemId);
		return rank >= 0 && rank < 4;
	}

	/** Canonical Main segment: axe, pickaxe, hammer, chisel, then spade. */
	public static int quickAccessRank(int itemId)
	{
		if (contains(tiers("AXE"), itemId)) return 0;
		if (contains(tiers("PICKAXE"), itemId)) return 1;
		if (contains(tiers("HAMMER"), itemId)) return 2;
		if (contains(tiers("CHISEL"), itemId)) return 3;
		if (itemId == 952) return 4;
		return -1;
	}

	private static void selectHighest(Set<Integer> owned, List<List<Integer>> tiers,
		Set<Integer> selected)
	{
		for (List<Integer> tier : tiers)
		{
			for (Integer itemId : tier)
			{
				if (owned.contains(itemId))
				{
					selected.add(itemId);
					return;
				}
			}
		}
	}

	private static boolean contains(List<List<Integer>> tiers, int itemId)
	{
		for (List<Integer> tier : tiers)
		{
			if (tier.contains(itemId)) return true;
		}
		return false;
	}

	private static List<List<Integer>> tiers(String family)
	{
		return new ArrayList<>(TABLE.group(family).values());
	}

}
