export async function DELETE({ params }) {
  return removeAccount(params.id);
}
