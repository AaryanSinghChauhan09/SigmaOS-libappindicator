#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AppIndicatorItem {
    pub id: String,
    pub icon_name: String,
    pub title: String,
}

#[derive(Debug, Default)]
pub struct AppIndicatorRegistry {
    items: Vec<AppIndicatorItem>,
}

impl AppIndicatorRegistry {
    pub fn new() -> Self { Self { items: Vec::new() } }
    pub fn register(&mut self, id: &str, icon: &str, title: &str) {
        self.items.push(AppIndicatorItem {
            id: id.to_string(),
            icon_name: icon.to_string(),
            title: title.to_string(),
        });
    }
    pub fn unregister(&mut self, id: &str) {
        self.items.retain(|i| i.id != id);
    }
    pub fn count(&self) -> usize { self.items.len() }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_app_indicator_registry_aaa() {
        // Arrange
        let mut reg = AppIndicatorRegistry::new();
        // Act
        reg.register("vpn", "network-vpn-symbolic", "VPN Active");
        reg.register("chat", "user-available-symbolic", "Chat Online");
        assert_eq!(reg.count(), 2);
        reg.unregister("vpn");
        // Assert
        assert_eq!(reg.count(), 1);
    }
}
