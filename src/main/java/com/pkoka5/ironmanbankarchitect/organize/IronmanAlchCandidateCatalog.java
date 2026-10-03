package com.pkoka5.ironmanbankarchitect.organize;

import com.pkoka5.ironmanbankarchitect.catalog.OrderedItemFamilies;
import com.pkoka5.ironmanbankarchitect.catalog.RequiredResource;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/**
 * Reviewed canonical IDs for common Slayer/bossing alch stock.
 *
 * <p>The list deliberately uses RuneLite's player-facing gameval constants:
 * noted, POH, Battle Royale, League, dummy, ornament and clue variants are not
 * inferred from display names and therefore cannot enter by collision.</p>
 */
final class IronmanAlchCandidateCatalog
{
	private static final RequiredResource<Set<Integer>> ITEM_IDS = new RequiredResource<>("alch candidates",
		() -> Collections.unmodifiableSet(new HashSet<>(new OrderedItemFamilies(
			IronmanAlchCandidateCatalog.class.getResourceAsStream(
				"/com/pkoka5/ironmanbankarchitect/catalog/alch-candidate-layout-families.tsv"), 82)
			.ids("alch.reviewed-candidates"))));

	private IronmanAlchCandidateCatalog()
	{
	}

	static boolean contains(int itemId)
	{
		return ITEM_IDS.get().contains(itemId);
	}
}
