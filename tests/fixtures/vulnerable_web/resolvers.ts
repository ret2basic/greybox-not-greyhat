export const resolvers = {
  Query: {
    account: (_root, args) => loadAccount(args.id),
  },
  Mutation: {
    transfer: (_root, args) => transfer(args),
  },
};
