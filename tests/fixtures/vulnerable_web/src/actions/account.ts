"use server";

export async function changeEmail(accountId: string, email: string) {
  return accounts.update(accountId, { email });
}
