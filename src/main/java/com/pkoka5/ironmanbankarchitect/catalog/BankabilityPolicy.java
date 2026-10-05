package com.pkoka5.ironmanbankarchitect.catalog;

import java.util.HashSet;
import java.util.Set;

/** Deposit suggestions only: observed bank rows must never be filtered through this policy. */
public final class BankabilityPolicy
{
	private static final RequiredResource<Set<Integer>> EXCLUDED = new RequiredResource<>(
		"bankability policy", () -> new HashSet<>(new OrderedItemFamilies(
			BankabilityPolicy.class.getResourceAsStream("non-bankable-item-ids.tsv"), 719).ids("non-bankable")));

	private BankabilityPolicy() { }

	/** Unknown bankability is not a prohibition; this does not assert positive depositability. */
	public static boolean maySuggestDeposit(int itemId)
	{
		// Ideology of Darkness: own Wiki revision 15311009 documents the deposit prohibition.
		return itemId > 0 && itemId != 13532 && !EXCLUDED.get().contains(itemId);
	}
}
