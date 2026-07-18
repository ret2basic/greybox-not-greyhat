import org.springframework.web.bind.annotation.*;

@RestController
public class AccountController {
    @DeleteMapping("/admin/accounts/{id}")
    public void remove(@RequestParam String id) {
    }
}
