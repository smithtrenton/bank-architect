package com.pkoka5.ironmanbankarchitect.bank;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.assertEquals;

import net.runelite.api.gameval.ItemID;
import org.junit.Test;

public class BankSnapshotReaderTest
{
	@Test
	public void bankFillerIsSkipped()
	{
		assertFalse(BankSnapshotReader.isSnapshotItem(ItemID.BANK_FILLER, 1));
	}

	@Test
	public void invalidItemsAreSkipped()
	{
		assertFalse(BankSnapshotReader.isSnapshotItem(0, 1));
		assertFalse(BankSnapshotReader.isSnapshotItem(-1, 1));
		assertFalse(BankSnapshotReader.isSnapshotItem(209, 0));
		assertFalse(BankSnapshotReader.isSnapshotItem(209, -1));
	}

	@Test
	public void validBankItemsAreAccepted()
	{
		assertTrue(BankSnapshotReader.isSnapshotItem(209, 1));
		for (int itemId : new int[] {2875, 13183, 13184, 13532, 6643, 4678, 10835, 30808})
		{
			assertTrue(BankSnapshotReader.isSnapshotItem(itemId, 1));
			assertEquals(itemId, BankSnapshotReader.snapshotItem(itemId, 1, -1, -1, 4)
				.orElseThrow(() -> new AssertionError("observed row lost")).getItemId());
		}
	}

	@Test
	public void placeholderVariantIsCanonicalizedAndPreservedAtZeroQuantity()
	{
		BankItemSnapshot placeholder = BankSnapshotReader.snapshotItem(50000, 0, 14401, 6687, 27)
			.orElseThrow(() -> new AssertionError("expected placeholder"));

		assertEquals(6687, placeholder.getItemId());
		assertEquals(0, placeholder.getQuantity());
		assertEquals(27, placeholder.getSlotIndex());
		assertTrue(placeholder.isPlaceholder());
		BankItemSnapshot nonBankablePlaceholder = BankSnapshotReader.snapshotItem(50000, 0, 14401, 2875, 28)
			.orElseThrow(() -> new AssertionError("observed placeholder lost"));
		assertEquals(2875, nonBankablePlaceholder.getItemId());
		assertEquals(0, nonBankablePlaceholder.getQuantity());
		assertTrue(nonBankablePlaceholder.isPlaceholder());
	}

	@Test
	public void ordinaryZeroQuantitySlotIsStillSkipped()
	{
		assertFalse(BankSnapshotReader.snapshotItem(6687, 0, -1, 50000, 1).isPresent());
	}
}
