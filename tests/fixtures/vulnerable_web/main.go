package main

func routes(router *Router) {
    router.GET("/teams/:id", getTeam)
}
